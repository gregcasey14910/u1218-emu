import sys, cv2, numpy as np
src, out = sys.argv[1], sys.argv[2]
img = cv2.imread(src)
up = cv2.resize(img, None, fx=4, fy=4, interpolation=cv2.INTER_LANCZOS4)
up = cv2.fastNlMeansDenoisingColored(up, None, 5, 5, 7, 21)
lab = cv2.cvtColor(up, cv2.COLOR_BGR2LAB)
l, a, b = cv2.split(lab)
l = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(16, 16)).apply(l)
up = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)
blur = cv2.GaussianBlur(up, (0, 0), 3)
up = cv2.addWeighted(up, 1.6, blur, -0.6, 0)
cv2.imwrite(out, up, [cv2.IMWRITE_JPEG_QUALITY, 92])
print(up.shape)
