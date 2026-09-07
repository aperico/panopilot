import math
import numpy as np
from panopilot.stabilization import adaptive_profile, build_adaptive_trajectory, sample_trajectory

def _qz(deg):
    a=math.radians(deg)/2.0
    return [math.cos(a),0.0,0.0,math.sin(a)]

def _yaw_deg(q):
    w,x,y,z=q
    return math.degrees(math.atan2(2*(w*z+x*y),1-2*(y*y+z*z)))

def _samples(rate=1000.0,duration=4.0):
    times=np.arange(0.0,duration,1.0/rate)
    yaw=8.0*times+3.0*np.sin(2*np.pi*8.0*times)+1.2*np.sin(2*np.pi*21.0*times)
    return [{"source_time":float(t),"quat":_qz(float(y)),"source":"highrate"} for t,y in zip(times,yaw)]

def test_highrate_adaptive_strongly_reduces_high_frequency_motion():
    traj=build_adaptive_trajectory(_samples(),0.85)
    raw=np.unwrap(np.radians([_yaw_deg(q) for q in traj.raw_quaternions]))
    stable=np.unwrap(np.radians([_yaw_deg(q) for q in traj.stable_quaternions]))
    # Second difference rejects constant/slow pan and measures rapid angular
    # oscillation. The adaptive trajectory should suppress it strongly.
    raw_hf=float(np.sqrt(np.mean(np.diff(raw, n=2)**2)))
    stable_hf=float(np.sqrt(np.mean(np.diff(stable, n=2)**2)))
    assert stable_hf < raw_hf*0.20

def test_sustained_fast_turn_is_followed_instead_of_world_locked():
    rate=1000.0
    times=np.arange(0.0,2.0,1.0/rate)
    yaw=220.0*times
    samples=[{"source_time":float(t),"quat":_qz(float(y)),"source":"highrate"} for t,y in zip(times,yaw)]
    traj=build_adaptive_trajectory(samples,0.85)
    stable=np.unwrap(np.radians([_yaw_deg(q) for q in traj.stable_quaternions]))
    # Ignore filter edge transients; the center must retain substantial fast
    # deliberate rotation.
    i0=int(0.6*rate); i1=int(1.4*rate)
    followed=math.degrees(stable[i1]-stable[i0])/(traj.times[i1]-traj.times[i0])
    assert followed > 100.0

def test_amount_zero_keeps_native_trajectory_exactly():
    traj=build_adaptive_trajectory(_samples(rate=200.0,duration=1.0),0.0)
    assert np.array_equal(traj.raw_quaternions,traj.stable_quaternions)

def test_70_percent_profile_is_strong_and_adaptive():
    p=adaptive_profile(0.70)
    assert p["correction_gain"] > 0.95
    assert p["low_velocity_tau_s"] > 1.5
    assert p["high_velocity_tau_s"] < p["low_velocity_tau_s"]

def test_exposure_sampling_uses_native_highrate_trajectory():
    traj=build_adaptive_trajectory(_samples(rate=1000.0,duration=1.0),0.8)
    exposure=np.arange(0.0,0.9,1.0/30.0)
    raw,stable=sample_trajectory(traj,exposure)
    assert len(raw)==len(exposure) and len(stable)==len(exposure)
    assert traj.diagnostics["sample_rate_hz"] > 900.0
    assert traj.diagnostics["algorithm"] == "adaptive-highrate-v1"
