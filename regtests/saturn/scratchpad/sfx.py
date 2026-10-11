import wave,array,math,sys
fn=sys.argv[1]
w=wave.open(fn,'rb'); d=array.array('h'); d.frombytes(w.readframes(w.getnframes()))
sr=w.getframerate()
m=[(d[i]+d[i+1])/2 for i in range(0,len(d)-1,2)]
win=sr//100
hp=[]
for i in range(0,len(m)-win,win):
    s=0
    for j in range(i+1,i+win):
        x=m[j]-m[j-1]; s+=x*x
    hp.append(math.sqrt(s/win))
ons=[]
for i in range(100,len(hp)):
    med=sorted(hp[i-100:i])[50]
    if hp[i]>3*med+200 and (not ons or i-ons[-1]>10): ons.append(i)
ts=[o/100 for o in ons]
print(fn, ' '.join('%d-%d:%d'%(lo,hi,sum(1 for t in ts if lo<=t<hi)) for lo,hi in ((0,55),(55,90),(90,120),(120,150),(150,180))))
