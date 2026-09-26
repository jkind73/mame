import struct, sys
from PIL import Image
def frames(path):
    d=open(path,'rb').read(); p=0; out=[]
    while p+8<=len(d):
        w,h=struct.unpack('<II',d[p:p+8]); p+=8; out.append((w,h,d[p:p+w*h*4])); p+=w*h*4
    return out
c=int(sys.argv[1]); pre=sys.argv[2]
w,h,a=frames('vf/%s_y.bin'%pre)[c]; _,_,b=frames('vf/%s_a.bin'%pre)[c]
ia=Image.frombytes('RGBA',(w,h),a).convert('RGB')
bb=bytearray()
for k in range(0,len(b),4): bb+=bytes((b[k+2],b[k+1],b[k]))
ib=Image.frombytes('RGB',(w,h),bytes(bb))
d=Image.new('RGB',(w,h))
pa,pb=ia.load(),ib.load(); pd=d.load()
for y in range(h):
    for x in range(w):
        pd[x,y]=(255,0,0) if max(abs(pa[x,y][i]-pb[x,y][i]) for i in range(3))>8 else (0,0,0)
o=Image.new('RGB',(w*3,h)); o.paste(ia,(0,0)); o.paste(ib,(w,0)); o.paste(d,(2*w,0)); o.save('vf/%s_%d.png'%(pre,c))
