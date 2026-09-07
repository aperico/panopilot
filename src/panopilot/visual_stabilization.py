"""
Hybrid visual residual stabilization for conventional PanoPilot output.

The gyro stage removes 3-axis camera rotation. This stage estimates residual
image-space motion after gyro stabilization and removes the remaining bobbing,
translation, small rotational error, parallax residual, and timing/calibration
error with a constrained 2D similarity correction plus a fixed center crop.

The implementation is intentionally export-stage and opt-in in 0.31. The
accepted Project Preview/final semantic baseline remains unchanged until this
spike is visually accepted on representative media.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import subprocess
import time

import cv2
import numpy as np


@dataclass(frozen=True)
class VisualStabilizationPlan:
    dx: np.ndarray
    dy: np.ndarray
    angle_deg: np.ndarray
    applied_ratio: np.ndarray
    crop_percent: float
    analysis_width: int
    analysis_height: int
    sigma_frames: float
    diagnostics: dict


def _gaussian_smooth(values, sigma_frames):
    values=np.asarray(values,dtype=np.float64)
    sigma=float(sigma_frames)
    if len(values)==0 or sigma<=1e-9:
        return values.copy()
    radius=max(1,int(math.ceil(3.0*sigma)))
    x=np.arange(-radius,radius+1,dtype=np.float64)
    kernel=np.exp(-0.5*(x/sigma)**2)
    kernel/=kernel.sum()
    padded=np.pad(values,(radius,radius),mode='edge')
    return np.convolve(padded,kernel,mode='valid')


def _fill_invalid(values, valid):
    values=np.asarray(values,dtype=np.float64)
    valid=np.asarray(valid,dtype=bool)
    if len(values)==0:
        return values.copy()
    indices=np.arange(len(values),dtype=np.float64)
    good=np.flatnonzero(valid & np.isfinite(values))
    if len(good)==0:
        return np.zeros_like(values)
    if len(good)==1:
        return np.full_like(values,float(values[good[0]]))
    return np.interp(indices,good.astype(np.float64),values[good])


def _estimate_similarity_motion(previous_gray,current_gray):
    height,width=previous_gray.shape[:2]
    mask=np.zeros_like(previous_gray,dtype=np.uint8)
    # Avoid the most distorted / transient edge pixels while retaining broad
    # scene coverage for RANSAC.
    bx=max(8,int(round(width*0.04)))
    by=max(8,int(round(height*0.04)))
    mask[by:height-by,bx:width-bx]=255

    points=cv2.goodFeaturesToTrack(
        previous_gray,
        maxCorners=600,
        qualityLevel=0.01,
        minDistance=7,
        blockSize=7,
        mask=mask,
    )
    if points is None or len(points)<24:
        return None

    next_points,status,_error=cv2.calcOpticalFlowPyrLK(
        previous_gray,
        current_gray,
        points,
        None,
        winSize=(21,21),
        maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,30,0.01),
    )
    if next_points is None or status is None:
        return None
    p0=points[status.reshape(-1)==1].reshape(-1,2)
    p1=next_points[status.reshape(-1)==1].reshape(-1,2)
    if len(p0)<24:
        return None

    matrix,inliers=cv2.estimateAffinePartial2D(
        p0,p1,
        method=cv2.RANSAC,
        ransacReprojThreshold=1.75,
        maxIters=3000,
        confidence=0.995,
        refineIters=10,
    )
    if matrix is None:
        return None

    inlier_count=int(inliers.sum()) if inliers is not None else 0
    inlier_ratio=float(inlier_count/max(1,len(p0)))
    if inlier_count<24 or inlier_ratio<0.22:
        return None

    a=float(matrix[0,0]); b=float(matrix[0,1])
    scale=math.sqrt(a*a+b*b)
    angle_deg=math.degrees(math.atan2(float(matrix[1,0]),float(matrix[0,0])))
    if not 0.90<=scale<=1.10 or abs(angle_deg)>15.0:
        return None

    center=np.array([width/2.0,height/2.0,1.0],dtype=np.float64)
    moved=matrix@center
    dx=float(moved[0]-center[0])
    dy=float(moved[1]-center[1])
    return {
        'dx':dx,
        'dy':dy,
        'angle_deg':angle_deg,
        'inliers':inlier_count,
        'inlier_ratio':inlier_ratio,
    }


def _correction_matrix(width,height,dx,dy,angle_deg,alpha=1.0):
    alpha=float(alpha)
    matrix=cv2.getRotationMatrix2D(
        (width/2.0,height/2.0),
        -float(angle_deg)*alpha,
        1.0,
    )
    matrix[0,2]+=float(dx)*alpha
    matrix[1,2]+=float(dy)*alpha
    return matrix.astype(np.float64)


def _crop_corners(width,height,crop_percent):
    retain=1.0-float(crop_percent)/100.0
    crop_w=float(width)*retain
    crop_h=float(height)*retain
    x0=(float(width)-crop_w)/2.0
    y0=(float(height)-crop_h)/2.0
    return np.array([
        [x0,y0],
        [x0+crop_w,y0],
        [x0+crop_w,y0+crop_h],
        [x0,y0+crop_h],
    ],dtype=np.float32)


def _correction_fits_crop(width,height,crop_percent,dx,dy,angle_deg,alpha):
    matrix=_correction_matrix(width,height,dx,dy,angle_deg,alpha)
    source=np.array([
        [0.0,0.0,1.0],
        [float(width),0.0,1.0],
        [float(width),float(height),1.0],
        [0.0,float(height),1.0],
    ],dtype=np.float64)
    polygon=(matrix@source.T).T.astype(np.float32)
    crop=_crop_corners(width,height,crop_percent)
    return all(
        cv2.pointPolygonTest(polygon,tuple(map(float,point)),False)>=-1e-4
        for point in crop
    )


def _max_feasible_alpha(width,height,crop_percent,dx,dy,angle_deg):
    if crop_percent<=0.0:
        return 0.0
    if _correction_fits_crop(width,height,crop_percent,dx,dy,angle_deg,1.0):
        return 1.0
    lo=0.0; hi=1.0
    for _ in range(14):
        mid=(lo+hi)/2.0
        if _correction_fits_crop(width,height,crop_percent,dx,dy,angle_deg,mid):
            lo=mid
        else:
            hi=mid
    return lo


def analyze_visual_stabilization(
    input_video,
    frame_segments,
    *,
    amount,
    crop_percent=25.0,
    analysis_width=640,
):
    input_video=Path(input_video)
    amount=max(0.0,min(1.0,float(amount)))
    crop_percent=float(crop_percent)
    if not 0.0<=crop_percent<=40.0:
        raise ValueError('crop_percent must be between 0 and 40')

    cap=cv2.VideoCapture(str(input_video))
    if not cap.isOpened():
        raise RuntimeError(f'Could not open rendered video for visual stabilization: {input_video}')
    fps=float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    if fps<=0.0 or frame_count<=0 or width<=0 or height<=0:
        cap.release()
        raise RuntimeError('Rendered video metadata is invalid for visual stabilization')

    analysis_width=max(160,min(int(analysis_width),width))
    analysis_height=max(90,int(round(height*analysis_width/width)))
    segment_starts={int(start) for start,_count in frame_segments}

    motion_dx=np.full(frame_count,np.nan,dtype=np.float64)
    motion_dy=np.full(frame_count,np.nan,dtype=np.float64)
    motion_angle=np.full(frame_count,np.nan,dtype=np.float64)
    inlier_ratios=[]
    previous_gray=None

    for frame_index in range(frame_count):
        ok,frame=cap.read()
        if not ok:
            cap.release()
            raise RuntimeError(f'Visual-stabilization analysis ended at frame {frame_index}/{frame_count}')
        small=cv2.resize(frame,(analysis_width,analysis_height),interpolation=cv2.INTER_AREA)
        gray=cv2.cvtColor(small,cv2.COLOR_BGR2GRAY)
        if frame_index in segment_starts:
            previous_gray=gray
            motion_dx[frame_index]=0.0
            motion_dy[frame_index]=0.0
            motion_angle[frame_index]=0.0
            continue
        estimate=_estimate_similarity_motion(previous_gray,gray) if previous_gray is not None else None
        if estimate is not None:
            motion_dx[frame_index]=estimate['dx']
            motion_dy[frame_index]=estimate['dy']
            motion_angle[frame_index]=estimate['angle_deg']
            inlier_ratios.append(estimate['inlier_ratio'])
        previous_gray=gray
    cap.release()

    correction_dx=np.zeros(frame_count,dtype=np.float64)
    correction_dy=np.zeros(frame_count,dtype=np.float64)
    correction_angle=np.zeros(frame_count,dtype=np.float64)

    # At 100%, a ~0.55 s sigma strongly suppresses walking/bobbing frequencies.
    # Amount changes both path bandwidth and correction gain.
    sigma_seconds=0.12+0.43*amount
    sigma_frames=max(0.5,sigma_seconds*fps)
    gain=1.0-(1.0-amount)**2

    invalid_transitions=0
    for start,count in frame_segments:
        start=int(start); count=int(count); end=start+count
        if count<=0: continue
        local_dx=motion_dx[start:end].copy()
        local_dy=motion_dy[start:end].copy()
        local_angle=motion_angle[start:end].copy()
        valid=np.isfinite(local_dx)&np.isfinite(local_dy)&np.isfinite(local_angle)
        invalid_transitions+=int((~valid).sum())
        local_dx=_fill_invalid(local_dx,valid)
        local_dy=_fill_invalid(local_dy,valid)
        local_angle=_fill_invalid(local_angle,valid)
        local_dx[0]=0.0; local_dy[0]=0.0; local_angle[0]=0.0

        path_x=np.cumsum(local_dx)
        path_y=np.cumsum(local_dy)
        path_angle=np.cumsum(local_angle)
        smooth_x=_gaussian_smooth(path_x,sigma_frames)
        smooth_y=_gaussian_smooth(path_y,sigma_frames)
        smooth_angle=_gaussian_smooth(path_angle,sigma_frames)
        correction_dx[start:end]=(smooth_x-path_x)*gain
        correction_dy[start:end]=(smooth_y-path_y)*gain
        correction_angle[start:end]=(smooth_angle-path_angle)*gain

    scale_x=float(width)/float(analysis_width)
    scale_y=float(height)/float(analysis_height)
    correction_dx*=scale_x
    correction_dy*=scale_y

    applied=np.ones(frame_count,dtype=np.float64)
    for index in range(frame_count):
        applied[index]=_max_feasible_alpha(
            width,height,crop_percent,
            correction_dx[index],correction_dy[index],correction_angle[index],
        )
    correction_dx*=applied
    correction_dy*=applied
    correction_angle*=applied

    abs_translation=np.sqrt(correction_dx**2+correction_dy**2)
    diagnostics={
        'algorithm':'hybrid-gyro-plus-opticalflow-similarity-v1',
        'fps':fps,
        'frame_count':frame_count,
        'width':width,
        'height':height,
        'analysis_width':analysis_width,
        'analysis_height':analysis_height,
        'amount':amount,
        'crop_percent':crop_percent,
        'retained_linear_fraction':1.0-crop_percent/100.0,
        'output_zoom':1.0/max(1e-9,1.0-crop_percent/100.0),
        'sigma_seconds':sigma_seconds,
        'sigma_frames':sigma_frames,
        'invalid_motion_frames':invalid_transitions,
        'mean_inlier_ratio':float(np.mean(inlier_ratios)) if inlier_ratios else 0.0,
        'median_translation_correction_px':float(np.median(abs_translation)),
        'p95_translation_correction_px':float(np.percentile(abs_translation,95)),
        'max_translation_correction_px':float(np.max(abs_translation)),
        'p95_rotation_correction_deg':float(np.percentile(np.abs(correction_angle),95)),
        'max_rotation_correction_deg':float(np.max(np.abs(correction_angle))),
        'mean_applied_correction_ratio':float(np.mean(applied)),
        'p05_applied_correction_ratio':float(np.percentile(applied,5)),
        'crop_limited_frames':int(np.sum(applied<0.999)),
    }
    return VisualStabilizationPlan(
        dx=correction_dx,
        dy=correction_dy,
        angle_deg=correction_angle,
        applied_ratio=applied,
        crop_percent=crop_percent,
        analysis_width=analysis_width,
        analysis_height=analysis_height,
        sigma_frames=sigma_frames,
        diagnostics=diagnostics,
    )


def render_visual_stabilization(
    input_video,
    output_video,
    plan,
    *,
    crf=18,
    preset='medium',
    progress_callback=None,
):
    input_video=Path(input_video); output_video=Path(output_video)
    cap=cv2.VideoCapture(str(input_video))
    if not cap.isOpened():
        raise RuntimeError(f'Could not open visual-stabilization input: {input_video}')
    fps=float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    if frame_count!=len(plan.dx):
        cap.release()
        raise RuntimeError('Visual-stabilization plan frame count does not match rendered video')

    retain=1.0-plan.crop_percent/100.0
    crop_w=max(2,int(round(width*retain)))
    crop_h=max(2,int(round(height*retain)))
    crop_w-=crop_w%2; crop_h-=crop_h%2
    x0=(width-crop_w)//2; y0=(height-crop_h)//2

    cmd=[
        'ffmpeg','-y','-v','error',
        '-f','rawvideo','-pix_fmt','bgr24',
        '-s',f'{width}x{height}',
        '-r',f'{fps:.9f}',
        '-i','-','-an',
        '-c:v','libx264','-preset',str(preset),'-crf',str(int(crf)),
        '-pix_fmt','yuv420p','-movflags','+faststart',
        str(output_video),
    ]
    try:
        encoder=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    except FileNotFoundError as exc:
        cap.release()
        raise RuntimeError('ffmpeg was not found') from exc

    started=time.perf_counter()
    try:
        for index in range(frame_count):
            ok,frame=cap.read()
            if not ok:
                raise RuntimeError(f'Visual-stabilization render ended at frame {index}/{frame_count}')
            matrix=_correction_matrix(
                width,height,
                plan.dx[index],plan.dy[index],plan.angle_deg[index],1.0,
            )
            warped=cv2.warpAffine(
                frame,matrix,(width,height),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_REFLECT_101,
            )
            cropped=warped[y0:y0+crop_h,x0:x0+crop_w]
            stabilized=cv2.resize(cropped,(width,height),interpolation=cv2.INTER_LANCZOS4)
            try:
                encoder.stdin.write(stabilized.tobytes())
            except BrokenPipeError as exc:
                raise RuntimeError('Visual-stabilization H.264 encoder stopped unexpectedly') from exc
            if progress_callback and (index==0 or index+1==frame_count or (index+1)%15==0):
                progress_callback({
                    'stage':'visual-stabilization',
                    'message':f'Visual stabilization — {index+1}/{frame_count} frames ({100.0*(index+1)/frame_count:.1f}%)',
                    'frame':index+1,
                    'total_frames':frame_count,
                })
    finally:
        cap.release()
        if encoder.stdin:
            encoder.stdin.close()
        stderr=encoder.stderr.read().decode('utf-8','replace') if encoder.stderr else ''
        encoder.wait()
    if encoder.returncode!=0:
        raise RuntimeError('Visual-stabilization H.264 encoding failed:\n'+stderr)
    return {
        **plan.diagnostics,
        'processing_seconds':float(time.perf_counter()-started),
        'encoder_crf':int(crf),
        'encoder_preset':str(preset),
    }


def stabilize_rendered_video(
    input_video,
    output_video,
    frame_segments,
    *,
    amount,
    crop_percent=25.0,
    analysis_width=640,
    crf=18,
    preset='medium',
    progress_callback=None,
):
    if progress_callback:
        progress_callback({'stage':'visual-analysis','message':'Analyzing residual visual motion'})
    analysis_started=time.perf_counter()
    plan=analyze_visual_stabilization(
        input_video,frame_segments,
        amount=amount,
        crop_percent=crop_percent,
        analysis_width=analysis_width,
    )
    analysis_seconds=time.perf_counter()-analysis_started
    if progress_callback:
        progress_callback({'stage':'visual-stabilization','message':f'Applying residual stabilization with {crop_percent:.0f}% crop reserve'})
    result=render_visual_stabilization(
        input_video,output_video,plan,
        crf=crf,preset=preset,progress_callback=progress_callback,
    )
    result['analysis_seconds']=float(analysis_seconds)
    result['total_seconds']=float(analysis_seconds+result['processing_seconds'])
    return result
