\
import cv2
import numpy as np

from panopilot.direct_render import DirectLensRenderer

class FakeMapper: pass

def fake_mapper(width=240,height=120):
    m=FakeMapper()
    xx=np.broadcast_to(np.arange(width,dtype=np.float32)[None,:],(height,width)).copy()
    yy=np.broadcast_to(np.arange(height,dtype=np.float32)[:,None],(height,width)).copy()
    m.map0_x=xx; m.map0_y=yy; m.map1_x=xx; m.map1_y=yy
    ramp=np.linspace(1.0,0.0,width,dtype=np.float32)[None,:]
    m.w0=np.broadcast_to(ramp,(height,width)).copy()
    m.w1=(1.0-m.w0).astype(np.float32)
    m.uncovered=np.zeros((height,width),dtype=bool)
    return m

def test_direct_map_identity_geometry():
    r=DirectLensRenderer(fake_mapper())
    mx=np.array([[10.0,50.25,100.5,200.0]],dtype=np.float32)
    my=np.array([[20.0,30.5,60.25,90.0]],dtype=np.float32)
    maps=r.compose_maps(mx,my)
    assert np.allclose(maps.lens0_x,mx,atol=0.003)
    assert np.allclose(maps.lens0_y,my,atol=0.003)
    assert np.allclose(maps.weight0+maps.weight1,1.0,atol=1e-6)

def test_direct_matches_two_stage_for_smooth_identity_maps():
    width,height=240,120
    m=fake_mapper(width,height); r=DirectLensRenderer(m)
    x=np.linspace(0,255,width,dtype=np.float32)[None,:]
    y=np.linspace(0,255,height,dtype=np.float32)[:,None]
    l0=np.empty((height,width,3),np.uint8); l1=np.empty_like(l0)
    l0[...,0]=x.astype(np.uint8); l0[...,1]=y.astype(np.uint8); l0[...,2]=40
    l1[...,0]=(255-x).astype(np.uint8); l1[...,1]=y.astype(np.uint8); l1[...,2]=180
    ow,oh=120,60
    mx=np.broadcast_to(np.linspace(10,width-11,ow,dtype=np.float32)[None,:],(oh,ow)).copy()
    my=np.broadcast_to(np.linspace(10,height-11,oh,dtype=np.float32)[:,None],(oh,ow)).copy()
    p0=cv2.remap(l0,m.map0_x,m.map0_y,cv2.INTER_LINEAR)
    p1=cv2.remap(l1,m.map1_x,m.map1_y,cv2.INTER_LINEAR)
    pano=cv2.blendLinear(p0,p1,m.w0,m.w1)
    ref=cv2.remap(pano,mx,my,cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
    direct=r.render(l0,l1,r.compose_maps(mx,my))
    diff=cv2.absdiff(ref,direct)
    assert int(diff.max()) <= 2
    assert float(diff.mean()) < 0.2
