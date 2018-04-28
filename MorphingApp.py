import sys
from Morphing import *
from PySide.QtGui import *
from PySide.QtCore import *
from MorphingGUI import *


class MorphingConsumer(QMainWindow, Ui_MainWindow):

    def __init__(self, parent=None):

        super(MorphingConsumer, self).__init__(parent)
        self.setupUi(self)

        self.startLoaded = False
        self.endLoaded = False
        self.startImageArray = None
        self.startPoints = np.empty(shape=(1, 2))
        self.endPoints = np.empty(shape=(1, 2))
        self.endImageArray = None
        self.currentStartPoint = None
        self.currentEndPoint = None
        self.startTriangles = []
        self.endTriangles = []

        # Attach events
        self.loadStartButton.clicked.connect(self.LoadStartImage)
        self.loadEndButton.clicked.connect(self.LoadEndImage)
        self.alphaSlider.valueChanged.connect(self.DragAlpha)
        self.blendButton.clicked.connect(self.BlendImages)
        self.trianglesCheckBox.clicked.connect(self.DrawDelaunay)
        self.startingImage.mousePressEvent = self.DrawPointStart
        self.endImage.mousePressEvent = self.DrawPointEnd

        self.InitialState()


    def mousePressEvent(self, event):
        # If the two points exist then persist them on any click
        if self.currentStartPoint is not None and self.currentEndPoint is not None:
            # Persist the points
            self.PointPairAdded()


    def keyPressEvent(self, event):
        # On Backspace press
        if event.key() == Qt.Key_Backspace and self.currentStartPoint is not None and self.currentEndPoint is not None:
            # Remove the end point from the view
            self.currentEndEllipse.setVisible(False)
            self.currentEndPoint = None
        elif event.key() == Qt.Key_Backspace and self.currentStartPoint is not None:
            # Remove the start point from the view
            self.currentStartEllipse.setVisible(False)
            self.currentStartPoint = None


    def BlendImages(self):
        # Blend the two images together

        blendedImage = self.blender.getBlendedImage(self.alpha)

        # Display the image
        scene = QGraphicsScene(self)

        # Convert output blended image to displayable form
        if len(blendedImage.shape) == 3:
            blendedMap = QPixmap.fromImage(QImage(blendedImage.data, blendedImage.shape[1], blendedImage.shape[0], blendedImage.strides[0], QImage.Format_RGB888))
        else:
            blendedMap = QPixmap.fromImage(QImage(blendedImage.data, blendedImage.shape[1], blendedImage.shape[0], blendedImage.strides[0], QImage.Format_Indexed8))

        # Scale appropriately
        scene.addPixmap(blendedMap)
        self.blendImage.setScene(scene)
        self.blendImage.fitInView(scene.sceneRect())


    def DrawPointStart(self, mouseEvent):

        self.mousePressEvent(mouseEvent)
        # Only can draw on the starting image if there isnt already a point there
        if self.endImageArray is not None and (self.currentStartPoint is None or self.currentEndPoint is not None):
            # Find the actual point in the image
            scenePoint = self.startingImage.mapToScene(mouseEvent.pos())

            # Set the current Point at the end
            roundedPoint = scenePoint.toPoint()
            self.currentStartPoint = [np.float64(roundedPoint.x()), np.float64(roundedPoint.y())]

            # Scene point is relative to the actual image -- good but need to get rid of white space
            #print(scenePoint)

            # Draw the ellipse using a QBrush -- make it green
            brush = QBrush(Qt.green)
            self.currentStartEllipse = QGraphicsEllipseItem(0, 0, 10, 10)
            self.currentStartEllipse.setBrush(brush)
            self.currentStartEllipse.setPos(scenePoint)
            self.startingImage.scene().addItem(self.currentStartEllipse)
            self.startingImage.fitInView(self.startingImage.scene().sceneRect())


    def DrawPointEnd(self, mouseEvent):

        # Only can draw on the ending image if there is a point on the start image
        if self.startImageArray is not None and self.currentStartPoint is not None and self.currentEndPoint is None:
            # Find the actual point in the image
            scenePoint = self.endImage.mapToScene(mouseEvent.pos())

            # Set the current Point at the end
            roundedPoint = scenePoint.toPoint()
            self.currentEndPoint = [np.float64(roundedPoint.x()), np.float64(roundedPoint.y())]

            # Scene point is relative to the actual image -- good but need to get rid of white space
            #print(scenePoint)

            # Draw the ellipse using a QBrush -- make it green
            brush = QBrush(Qt.green)
            self.currentEndEllipse = QGraphicsEllipseItem(0, 0, 10, 10)
            self.currentEndEllipse.setBrush(brush)
            self.currentEndEllipse.setPos(scenePoint)
            self.endImage.scene().addItem(self.currentEndEllipse)
            self.endImage.fitInView(self.endImage.scene().sceneRect())


    def PointPairAdded(self):
        # Both points have been added -- add them to the starting and ending point lists and recreate the blender

        self.startPoints = np.append(self.startPoints, [self.currentStartPoint], axis=0)
        self.endPoints = np.append(self.endPoints, [self.currentEndPoint], axis=0)

        # Change the color from green to blue
        self.currentStartEllipse.setBrush(QColor(Qt.blue))
        self.currentEndEllipse.setBrush(QColor(Qt.blue))

        # Try to create the blender -- If you can't then keep the blend button and triangle checkbox disabled because there aren't enough poins
        try:
            # Always make the blender based on if its color or gray scale
            if len(self.startImageArray.shape) == 3:
                self.blender = ColorBlender(startImage=self.startImageArray, startPoints=self.startPoints, endImage=self.endImageArray, endPoints=self.endPoints)
            else:
                self.blender = Blender(startImage=self.startImageArray, startPoints=self.startPoints, endImage=self.endImageArray, endPoints=self.endPoints)

            self.trianglesCheckBox.setEnabled(True)
            self.blendButton.setEnabled(True)
        except:
            self.trianglesCheckBox.setEnabled(False)
            self.blendButton.setEnabled(False)

        # Check if triangles should be reevaluated -- do so if necessary
        if self.trianglesCheckBox.isChecked():
            # Remove current Triangles
            self.trianglesCheckBox.setChecked(False)
            self.DrawDelaunay()
            # Draw the new triangles
            self.trianglesCheckBox.setChecked(True)
            self.DrawDelaunay()

        # Save the points to their appropriate files
        np.savetxt(self.startPointFilePath, self.startPoints, fmt='%f')
        np.savetxt(self.endPointFilePath, self.endPoints, fmt='%f')

        # Current Points should be removed
        self.currentStartPoint = None
        self.currentEndPoint = None


    def DrawDelaunay(self):

        # Draw the delaunay triangles if checked
        if self.trianglesCheckBox.isChecked():
            # Draw all the triangles in both images
            for tri in self.blender.triangles.simplices:

                # Find actual points in source and target
                currentStartPoints = np.array([[self.startPoints[tri[0], 0], self.startPoints[tri[0], 1]],
                                               [self.startPoints[tri[1], 0], self.startPoints[tri[1], 1]],
                                               [self.startPoints[tri[2], 0], self.startPoints[tri[2], 1]]], np.float64)

                currentEndPoints = np.array([[self.endPoints[tri[0], 0], self.endPoints[tri[0], 1]],
                                             [self.endPoints[tri[1], 0], self.endPoints[tri[1], 1]],
                                             [self.endPoints[tri[2], 0], self.endPoints[tri[2], 1]]], np.float64)

                startLine1 = QGraphicsLineItem(QLineF(QPointF(QPoint(currentStartPoints[0][0], currentStartPoints[0][1])), QPointF(QPoint(currentStartPoints[1][0], currentStartPoints[1][1]))))
                startLine2 = QGraphicsLineItem(QLineF(QPointF(QPoint(currentStartPoints[1][0], currentStartPoints[1][1])), QPointF(QPoint(currentStartPoints[2][0], currentStartPoints[2][1]))))
                startLine3 = QGraphicsLineItem(QLineF(QPointF(QPoint(currentStartPoints[2][0], currentStartPoints[2][1])), QPointF(QPoint(currentStartPoints[0][0], currentStartPoints[0][1]))))

                endLine1 = QGraphicsLineItem(QLineF(QPointF(QPoint(currentEndPoints[0][0], currentEndPoints[0][1])), QPointF(QPoint(currentEndPoints[1][0], currentEndPoints[1][1]))))
                endLine2 = QGraphicsLineItem(QLineF(QPointF(QPoint(currentEndPoints[1][0], currentEndPoints[1][1])), QPointF(QPoint(currentEndPoints[2][0], currentEndPoints[2][1]))))
                endLine3 = QGraphicsLineItem(QLineF(QPointF(QPoint(currentEndPoints[2][0], currentEndPoints[2][1])), QPointF(QPoint(currentEndPoints[0][0], currentEndPoints[0][1]))))

                # Add the maps to a collection
                self.startTriangles.append(startLine1)
                self.startTriangles.append(startLine2)
                self.startTriangles.append(startLine3)

                self.endTriangles.append(endLine1)
                self.endTriangles.append(endLine2)
                self.endTriangles.append(endLine3)

            # Place them in the scene
            pen = QPen(Qt.cyan)
            for triangle in self.startTriangles:
                triangle.setPen(pen)
                self.startingImage.scene().addItem(triangle)

            for triangle in self.endTriangles:
                triangle.setPen(pen)
                self.endImage.scene().addItem(triangle)
        else:
            # Undraw all the triangles

            # Remove the start triangles
            for triangle in self.startTriangles:
                self.startingImage.scene().removeItem(triangle)

            # Remove the end triangles
            for triangle in self.endTriangles:
                self.endImage.scene().removeItem(triangle)

            self.startTriangles = []
            self.endTriangles = []


    def DragAlpha(self):
        # Update the text box -- How to restrict to .05 increment?
        self.alpha = round(self.alphaSlider.value() / 100, 2)

        self.alphaValueText.setText(str(self.alpha))


    def LoadStartImage(self):

        filePath = self.GetFilePath()

        if not filePath:
            return

        # Place the image in the box -- resize too

        # Store the images in this class
        self.startImageArray = np.array(Image.open(filePath))

        scene = QGraphicsScene(self)

        startingImagePixMap = QPixmap(filePath)

        scene.addPixmap(startingImagePixMap)
        self.startingImage.setScene(scene)

        # Removing KeepAscpectRatio worked fine but why the persisting border
        self.startingImage.fitInView(scene.sceneRect())

        self.startTriangles = []
        self.startLoaded = True

        # Load correspondences here

        # Check if file exists first
        self.startPointFilePath = filePath + '.txt'

        # Try to load the points if the file exists
        try:
            self.startPoints = np.loadtxt(self.startPointFilePath)

            # Draw the ellipse using a QBrush -- make it green
            brush = QBrush(Qt.red)

            for point in self.startPoints:

                # Draw the ellipses
                ellipse = QGraphicsEllipseItem(0, 0, 10, 10)
                ellipse.setBrush(brush)
                ellipse.setPos(QPointF(QPoint(point[0] - 5, point[1] - 5)))
                self.startingImage.scene().addItem(ellipse)
                self.startingImage.fitInView(self.startingImage.scene().sceneRect())
        except:
            pass

        self.IsLoaded()


    def LoadEndImage(self):

        filePath = self.GetFilePath()

        if not filePath:
            return

        # Place the image in the box -- resize too

        self.endImageArray = np.array(Image.open(filePath))
        self.endTriangles = []

        scene = QGraphicsScene(self)

        endImagePixMap = QPixmap(filePath)
        #self.endImagePixMap = self.endImagePixMap.scaled(self.endImage.width() - 3, self.endImage.height() - 2, Qt.KeepAspectRatio)

        scene.addPixmap(endImagePixMap)
        self.endImage.setScene(scene)
        self.endImage.fitInView(scene.sceneRect())

        self.endLoaded = True

        # Load correspondences if they exist here
        self.endPointFilePath = filePath + '.txt'

        # Try to load the correspondences -- they might not exist
        try:
            self.endPoints = np.loadtxt(self.endPointFilePath)

            # Draw the ellipse using a QBrush -- make it green
            brush = QBrush(Qt.red)

            for point in self.endPoints:

                # Draw the ellipses
                ellipse = QGraphicsEllipseItem(0, 0, 10, 10)
                ellipse.setBrush(brush)
                ellipse.setPos(QPointF(QPoint(point[0] - 5, point[1] - 5)))
                self.endImage.scene().addItem(ellipse)
                self.endImage.fitInView(self.endImage.scene().sceneRect())
        except:
            pass

        # Check if should change to next state
        self.IsLoaded()


    def IsLoaded(self):

        # Check if both images loaded
        if self.startLoaded and self.endLoaded:
            # Enable widgets
            self.alphaSlider.setEnabled(True)

            # Try to create the blender -- if you can't then disable the appropriate buttons
            try:
                # Check if grayscale or color first
                if len(self.startImageArray.shape) == 3:
                    self.blender = ColorBlender(startImage=self.startImageArray, startPoints=self.startPoints, endImage=self.endImageArray, endPoints=self.endPoints)
                else:
                    self.blender = Blender(startImage=self.startImageArray, startPoints=self.startPoints, endImage=self.endImageArray, endPoints=self.endPoints)

                self.trianglesCheckBox.setEnabled(True)
                self.blendButton.setEnabled(True)
            except:
                pass


    def GetFilePath(self):

        # Get the file from the dialog
        filePath, _ = QFileDialog.getOpenFileName(self, caption='Open Image ...', filter="Images (*.jpg *.png)")
        return filePath


    def InitialState(self):

        # Disable some widgets
        self.alphaSlider.setEnabled(False)
        self.alphaValueText.setEnabled(False)
        self.blendButton.setEnabled(False)
        self.trianglesCheckBox.setEnabled(False)

        # Enable load buttons
        self.loadStartButton.setEnabled(True)
        self.loadEndButton.setEnabled(True)

        # Set slider to initial value?
        self.alpha = 0
        self.alphaValueText.setText('0.0')



if __name__ == "__main__":
    # Run the app -- hope size is good
    currentApp = QApplication(sys.argv)
    currentForm = MorphingConsumer()
    currentForm.show()
    currentApp.exec_()
