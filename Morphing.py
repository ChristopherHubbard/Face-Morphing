import numpy as np
from scipy.spatial import Delaunay
from scipy.interpolate import interpn
from scipy.sparse import find
import imageio as io
from PIL import Image, ImageDraw

import os
import time

class Affine():

    def __init__(self, source, destination):

        if type(source) is not np.ndarray or type(destination) is not np.ndarray:
            raise ValueError("Array inputs are not numpy arrays.")
        elif source.shape != (3, 2) or destination.shape != (3, 2):
            raise ValueError("The dimensions of the source or destination arrays don't match the 3x2 expected.")
        elif source.dtype != "float64" or destination.dtype != "float64":
            raise ValueError("Values in either source or destination aren't np.float64.")

        self.source = source
        self.destination = destination
        self.matrix = self._CreateMatrix()
        self.inverseMatrix = np.linalg.inv(self.matrix)

    def transform(self, sourceImage, destinationImage):
        # Verify types
        if type(sourceImage) is not np.ndarray or type(destinationImage) is not np.ndarray:
            raise TypeError("Both inputs must be numpy arrays.")

        # Create Mask for the triangle
        mask = self._Mask(destinationImage)

        # Find indicies to place data at
        sparse = find(mask)

        # Use inverse matrix -- then use interpolation and assign to destination at this point
        destArray = np.array([sparse[1],
                              sparse[0],
                              np.full(sparse[1].shape, 1)])

        # Unpack result
        result = np.matmul(self.inverseMatrix, destArray)

        # Perform the interpolation here on x and y from result
        valuePoints = list(zip(result[1], result[0]))

        # Interpolate
        points = (np.arange(sourceImage.shape[0]), np.arange(sourceImage.shape[1]))
        #print(points)
        results = interpn(points=points, values=sourceImage, xi=valuePoints, bounds_error=False)

        # Assign to output
        # print(np.nan in sparse[1])
        destinationImage[sparse[0], sparse[1]] = np.round([item for item in results])

    # Method to create a mask of this image
    def _Mask(self, destinationImage):

        # Get height and width from destination image -- setup mask
        height = destinationImage.shape[0]
        width = destinationImage.shape[1]

        # Create mask in transform for destination triangle
        image = Image.new('L', (width, height), 0)

        # Draw the triangle, using tuple vertices and fill it in with a white value
        vertices = [(self.destination[0, 0], self.destination[0, 1]),
                    (self.destination[1, 0], self.destination[1, 1]),
                    (self.destination[2, 0], self.destination[2, 1])]

        ImageDraw.Draw(image).polygon(vertices, outline=255, fill=255)

        # Convert to numpy array
        return np.array(image)

    # Method to create the affine transformation matrix
    def _CreateMatrix(self):

        # Set up all the arrays
        A = np.array([[self.source[0, 0], self.source[0, 1], 1, 0, 0, 0],
                      [0, 0, 0, self.source[0, 0], self.source[0, 1], 1],
                      [self.source[1, 0], self.source[1, 1], 1, 0, 0, 0],
                      [0, 0, 0, self.source[1, 0], self.source[1, 1], 1],
                      [self.source[2, 0], self.source[2, 1], 1, 0, 0, 0],
                      [0, 0, 0, self.source[2, 0], self.source[2, 1], 1]], np.float64)

        b = np.array([[self.destination[0, 0]],
                      [self.destination[0, 1]],
                      [self.destination[1, 0]],
                      [self.destination[1, 1]],
                      [self.destination[2, 0]],
                      [self.destination[2, 1]]], np.float64)

        H = np.linalg.solve(A, b)

        #print(H)

        matrix = np.array([[H[0, 0], H[1, 0], H[2, 0]],
                           [H[3, 0], H[4, 0], H[5, 0]],
                           [0, 0, 1]], np.float64)

        #print(matrix)

        return matrix



class Blender():

    def __init__(self, startImage, startPoints, endImage, endPoints):

        if type(startImage) is not np.ndarray or type(startPoints) is not np.ndarray or type(endImage) is not np.ndarray or type(endPoints) is not np.ndarray:
            raise TypeError("Inputs must be numpy arrays.")

        self.startImage = startImage
        self.startPoints = startPoints
        self.endImage = endImage
        self.endPoints = endPoints

        # These triangles should be the same for all three images (source 1, 2 and target)
        self.triangles = Delaunay(self.startPoints)

    def getBlendedImage(self, alpha):

        # Easy way to get target points with correspondences
        targetPoints = (1 - alpha) * self.startPoints + alpha * self.endPoints

        # Generate blank images -- intermediates and blended
        targetStart = np.array(Image.new('L', (self.startImage.shape[1], self.startImage.shape[0]), 0), np.uint8)
        targetEnd = np.array(Image.new('L', (self.endImage.shape[1], self.endImage.shape[0]), 0), np.uint8)

        # Go through all the triangles and create the two intermediate images
        for tri in self.triangles.simplices:

            # Find actual points in source and target
            currentStartPoints = np.array([[self.startPoints[tri[0], 0], self.startPoints[tri[0], 1]],
                                           [self.startPoints[tri[1], 0], self.startPoints[tri[1], 1]],
                                           [self.startPoints[tri[2], 0], self.startPoints[tri[2], 1]]], np.float64)

            currentEndPoints = np.array([[self.endPoints[tri[0], 0], self.endPoints[tri[0], 1]],
                                         [self.endPoints[tri[1], 0], self.endPoints[tri[1], 1]],
                                         [self.endPoints[tri[2], 0], self.endPoints[tri[2], 1]]], np.float64)

            # Vertices of triangles in target image
            currentTargetPoints = np.array([[targetPoints[tri[0], 0], targetPoints[tri[0], 1]],
                                            [targetPoints[tri[1], 0], targetPoints[tri[1], 1]],
                                            [targetPoints[tri[2], 0], targetPoints[tri[2], 1]]], np.float64)

            # Create affine instances
            Affine(currentStartPoints, currentTargetPoints).transform(self.startImage, targetStart)
            Affine(currentEndPoints, currentTargetPoints).transform(self.endImage, targetEnd)

        # Perform the blend between the intermediate images -- uses alpha equation

        return ((1 - alpha) * targetStart + alpha * targetEnd).astype(dtype='uint8')

    def generateMorphVideo(self, targetFolderPath, sequenceLength, includeReversed = True):

        # Create the folder if it doesn't exist
        if not os.path.exists(targetFolderPath):
            try:
                os.makedirs(targetFolderPath)
            except OSError as e:
                pass

        # Create a list to store the filepaths and images
        imageList = []
        fileList = []

        # Save starting image
        self._SaveImage(self.startImage, targetFolderPath + '/' + self._FrameName(1))
        imageList.append(self.startImage)
        fileList.append(targetFolderPath + '/' + self._FrameName(1))

        # Generate in between images -- sequenceLength - 2 images -- make sure total number of images equals sequenceLength

        # Increment amount
        increment = float(1.0 / ((sequenceLength - 2) + 1))
        alpha = 0.0
        for i in range(sequenceLength - 2):
            # Get alpha value, save image, and append to the file list
            alpha += increment
            #print(alpha)
            image = self.getBlendedImage(alpha)
            self._SaveImage(image, targetFolderPath + '/' + self._FrameName(i + 1))

            # Append to lists
            imageList.append(image)
            fileList.append(targetFolderPath + '/' + self._FrameName(i + 1))

        self._SaveImage(self.endImage, targetFolderPath + '/' + self._FrameName(sequenceLength))
        imageList.append(self.endImage)
        fileList.append(targetFolderPath + '/' + self._FrameName(sequenceLength))

        # Create the reverse set of images -- keep increasing numbering
        if includeReversed:
            # Write out the image files starting at the end of the imageList
            seqNum = sequenceLength + 1
            # Traverse the images starting at the end
            for image in reversed(imageList):
                # Save the image, apend to the fileList, and increase the sequence number
                self._SaveImage(image, targetFolderPath + '/' + self._FrameName(seqNum))
                fileList.append(targetFolderPath + '/' + self._FrameName(seqNum))
                seqNum += 1

        # Now create the mp4 video
        writer = io.get_writer(targetFolderPath + '/' + 'morph.mp4', fps=5)

        # Write out to the mp4 video
        for im in fileList:
            writer.append_data(io.imread(im))

        # Close the image writer
        writer.close()

    def _FrameName(self, number):

        # Return formatted filename
        return 'frame{:03d}.jpg'.format(number)

    def _SaveImage(self, npArray, fileName):

        image = Image.fromarray(npArray)

        if image.mode != 'RGB':
            image = image.convert('RGB')

        image.save(fileName)



class ColorAffine(Affine):

    def __init__(self, source, destination):
        # Call base constructor
        super().__init__(source, destination)



class ColorBlender(Blender):

    def __init__(self, startImage, startPoints, endImage, endPoints):
        # Call the base constructor
        super().__init__(startImage, startPoints, endImage, endPoints)

    def getBlendedImage(self, alpha):

        # Easy way to get target points with correspondences
        targetPoints = (1 - alpha) * self.startPoints + alpha * self.endPoints

        # Generate blank images -- intermediates and blended
        targetStart = np.array(Image.new('RGB', (self.startImage.shape[1], self.startImage.shape[0]), (0, 0, 0)), np.uint8)
        targetEnd = np.array(Image.new('RGB', (self.endImage.shape[1], self.endImage.shape[0]), (0, 0, 0)), np.uint8)

        # Go through all the triangles and create the two intermediate images
        for tri in self.triangles.simplices:

            # Find actual points in source and target
            currentStartPoints = np.array([[self.startPoints[tri[0], 0], self.startPoints[tri[0], 1]],
                                           [self.startPoints[tri[1], 0], self.startPoints[tri[1], 1]],
                                           [self.startPoints[tri[2], 0], self.startPoints[tri[2], 1]]], np.float64)

            currentEndPoints = np.array([[self.endPoints[tri[0], 0], self.endPoints[tri[0], 1]],
                                         [self.endPoints[tri[1], 0], self.endPoints[tri[1], 1]],
                                         [self.endPoints[tri[2], 0], self.endPoints[tri[2], 1]]], np.float64)

            # Vertices of triangles in target image
            currentTargetPoints = np.array([[targetPoints[tri[0], 0], targetPoints[tri[0], 1]],
                                            [targetPoints[tri[1], 0], targetPoints[tri[1], 1]],
                                            [targetPoints[tri[2], 0], targetPoints[tri[2], 1]]], np.float64)

            # Create affine instances
            ColorAffine(currentStartPoints, currentTargetPoints).transform(self.startImage, targetStart)
            ColorAffine(currentEndPoints, currentTargetPoints).transform(self.endImage, targetEnd)

        # Perform the blend between the intermediate images -- uses alpha equation

        return ((1 - alpha) * targetStart + alpha * targetEnd).astype(dtype='uint8')



def TestBlendGray():
    # Read in jpg's to np array
    tigerImage = np.array(Image.open('Tiger2Gray.jpg'))
    wolfImage = np.array(Image.open('WolfGray.jpg'))

    tigerPoints = np.loadtxt('./Tiger2Gray.jpg.txt')
    wolfPoints = np.loadtxt('./WolfGray.jpg.txt')

    b = Blender(startImage=tigerImage, startPoints=tigerPoints, endImage=wolfImage, endPoints=wolfPoints)

    blendedArray = b.getBlendedImage(.5)

    b._SaveImage(blendedArray, 'FasterBlendedGray.jpg')

def TestMorphGray():
    # Read in jpg's to np array
    tigerImage = np.array(Image.open('Tiger2Gray.jpg'))
    wolfImage = np.array(Image.open('WolfGray.jpg'))

    tigerPoints = np.loadtxt('./Tiger2Gray.jpg.txt')
    wolfPoints = np.loadtxt('./WolfGray.jpg.txt')

    b = Blender(startImage=tigerImage, startPoints=tigerPoints, endImage=wolfImage, endPoints=wolfPoints)

    # Create the mp4 video
    b.generateMorphVideo(targetFolderPath="./video_test_gray", sequenceLength=40)

def TestBlendColor():
    # Read in jpg's to np array
    tigerImage = np.array(Image.open('Tiger2Color.jpg'))
    wolfImage = np.array(Image.open('WolfColor.jpg'))

    tigerPoints = np.loadtxt('./Tiger2Gray.jpg.txt')
    wolfPoints = np.loadtxt('./WolfGray.jpg.txt')

    b = ColorBlender(startImage=tigerImage, startPoints=tigerPoints, endImage=wolfImage, endPoints=wolfPoints)

    blendedArray = b.getBlendedImage(.5)

    b._SaveImage(blendedArray, 'FasterBlendedColor.jpg')

def TestMorphColor():
    # Read in jpg's to np array
    tigerImage = np.array(Image.open('Tiger2Color.jpg'))
    wolfImage = np.array(Image.open('WolfColor.jpg'))

    tigerPoints = np.loadtxt('./Tiger2Gray.jpg.txt')
    wolfPoints = np.loadtxt('./WolfGray.jpg.txt')

    b = ColorBlender(startImage=tigerImage, startPoints=tigerPoints, endImage=wolfImage, endPoints=wolfPoints)

    # Create the mp4 video
    b.generateMorphVideo(targetFolderPath="./video_test_color", sequenceLength=40)

def PersonalMorphColor():
    # Read in jpg's to np array
    chrisImage = np.array(Image.open('ChristopherHubbard.jpg'))
    shellyImage = np.array(Image.open('Shelly.jpg'))

    chrisPoints = np.loadtxt('./ChristopherHubbard.jpg.txt')
    shellyPoints = np.loadtxt('./Shelly.jpg.txt')

    b = ColorBlender(startImage=chrisImage, startPoints=chrisPoints, endImage=shellyImage, endPoints=shellyPoints)

    # Create the mp4 video
    b.generateMorphVideo(targetFolderPath="./personal_morph_sequence", sequenceLength=100)

if __name__ == "__main__":

    #chrisImage = np.array(Image.open('ChristopherHubbard.jpg'))
    # Test GrayScale
    #avg = 0
    #for i in range(100):
    #    start = time.time()
    #    TestBlendGray()
    #    avg += time.time() - start
    #    print("Gray: {} seconds".format(time.time() - start))

    #print("Average time gray: {} seconds".format(avg / 100))

    # Test Color
    #avg = 0
    #for i in range(100):
    #   start = time.time()
    #   TestBlendColor()
    #   avg += time.time() - start
    #   print("Color: {} seconds".format(time.time() - start))

    #print ("Average time color: {} seconds".format(avg / 100))
    # Create Video GrayScale
    TestMorphGray()

    # Create Video Color
    TestMorphColor()

    # Create Personal Morph Sequence
    #PersonalMorphColor()






