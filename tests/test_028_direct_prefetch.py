\
import numpy as np
from panopilot.direct_render import DirectLensRenderer, DirectMapPrefetcher
from panopilot.virtual_camera import RectilinearProjector, VirtualCamera
class M: pass

def mapper():
    w,h=360,180; m=M()
    xx=np.broadcast_to(np.arange(w,dtype=np.float32)[None,:],(h,w)).copy()
    yy=np.broadcast_to(np.arange(h,dtype=np.float32)[:,None],(h,w)).copy()
    m.map0_x=xx;m.map0_y=yy;m.map1_x=xx;m.map1_y=yy
    m.w0=np.full((h,w),0.5,np.float32);m.w1=np.full((h,w),0.5,np.float32)
    m.uncovered=np.zeros((h,w),bool);return m

def test_direct_prefetch_matches_sync():
    p=RectilinearProjector(360,180,160,90); r=DirectLensRenderer(mapper())
    c=VirtualCamera(17,-4,78)
    x,y=p.map(c); exp=r.compose_maps(x,y)
    with DirectMapPrefetcher(p,r,enabled=True) as q:
        q.submit(c,None); got=q.result().maps
    assert np.array_equal(got.lens0_x,exp.lens0_x)
    assert np.array_equal(got.weight0,exp.weight0)
