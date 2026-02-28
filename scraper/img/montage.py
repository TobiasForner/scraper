import numpy as np
import cv2


class Montage(object):
    def __init__(self, initial_image: np.ndarray, max_x: int | None = None):
        if max_x:
            self.x = min(max_x, initial_image.shape[1])
        else:
            self.x = initial_image.shape[1]
        if self.x != initial_image.shape[1]:
            self.montage = self.normalize_image(initial_image)
        else:
            self.montage = initial_image

    def append(self, image: np.ndarray):
        new_image = self.normalize_image(image)
        self.montage = np.concatenate((self.montage, new_image), 0)

    def multi_append(self, images: list[np.ndarray]):
        images = [self.normalize_image(im) for im in images]
        self.montage = np.concatenate([self.montage] + images, 0)

    def normalize_image(self, image: np.ndarray):
        image = image[:, :, :3]
        y, x = image.shape[0:2]
        new_y = y * float(self.x) / x
        new_y = int(new_y)
        new_image = cv2.resize(image, (self.x, new_y))
        return new_image

    def show(self):
        cv2.imshow("montage", self.montage)
        cv2.waitKey()
        cv2.destroyAllWindows()

    def save(self, filename: str):
        print("Saving to", filename)
        cv2.imwrite(filename, self.montage)
        cv2.waitKey(0)
