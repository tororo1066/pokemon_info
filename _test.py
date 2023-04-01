# 560 875
import glob

from PIL import Image

for f in glob.glob("compareImages/changer/*.png"):
    im = Image.open(f)
    crop = im.crop((565, 875, 635, 910))
    crop.save("compareImages/changed/" + f.split("\\")[1])
