"""Compose the README installer showcase: make_showcase.py OUT.png SNAPSHOT_DIR"""
import sys
from PIL import Image, ImageDraw, ImageFilter
d=sys.argv[2].rstrip('/')+'/'  # folder with na_home/na_installing/na_installed.png (launcher --snapshot, empty --art)
ims=[Image.open(d+f'na_{s}.png').convert('RGB') for s in ('home','installing','installed')]
w,h=ims[0].size; pad=60; gap=40
W=pad*2+w*3+gap*2; H=pad*2+h
bg=Image.new('RGB',(W,H),(13,17,23))
for i,im in enumerate(ims):
    x=pad+i*(w+gap); y=pad
    sh=Image.new('L',(W,H),0); ImageDraw.Draw(sh).rounded_rectangle([x+6,y+14,x+w+6,y+h+14],12,fill=200)
    bg.paste((0,0,0),(0,0),sh.filter(ImageFilter.GaussianBlur(18)))
    m=Image.new('L',(w,h),0); ImageDraw.Draw(m).rounded_rectangle([0,0,w-1,h-1],10,fill=255)
    bg.paste(im,(x,y),m)
    ImageDraw.Draw(bg).rounded_rectangle([x,y,x+w-1,y+h-1],10,outline=(70,62,50),width=2)
bg.save(sys.argv[1],optimize=True); print(bg.size)
