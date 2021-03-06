#!/usr/bin/env python

# Import libraries
import os
import cv2
import numpy as np
import rospy

from cv_bridge import CvBridge
from sensor_msgs.msg import Image, CompressedImage
from std_msgs.msg import Float32MultiArray


# Get absolute base path for the folder containing the scripts
base_path = os.path.dirname(os.path.abspath(__file__))


class StopSignDetection:
    """
    Stop Sign Detection class for detecting stop sign using CV
    """

    def __init__(self, node_name):
        """
        Init function for TagFollower class
        """
        # Creates a node with the specified name and make sure it is a
        # unique node (using anonymous=True).
        rospy.init_node(node_name, anonymous=True)

        # Init bridge object
        self.bridge_object = CvBridge()

        # Init the work mode (simulation or real-world)
        self.work_mode = rospy.get_param('~work_mode')

        if self.work_mode == 'simulation':
            # Subscriber which will get images from the topic
            # '/camera/rgb/image_raw'
            self.image_sub = rospy.Subscriber(
                "/camera/rgb/image_raw",
                Image,
                self.camera_callback
            )
        else:
            # Subscriber which will get images from the topic
            # '/raspicam_node/image/compressed'
            self.image_sub = rospy.Subscriber(
                "/raspicam_node/image/compressed",
                CompressedImage,
                self.camera_callback
            )

        # Publisher which will publish to the topic '/stop_sign'
        self.stop_sign_pub = rospy.Publisher(
            '/stop_sign',
            Float32MultiArray,
            queue_size=10
        )

        # Init the stop sign message
        self.stop_sign_msg = Float32MultiArray()

        # Init the publish rate
        self.rate = rospy.Rate(10)

        # Init the stop sign classifier
        self.stop_sign_classifier = cv2.CascadeClassifier(
            os.path.join(
                base_path,
                'stop_sign_classifier.xml'
            )
        )


    def camera_callback(self, image):
        """
        Function for camera callback that is called everytime data is
        published to the camera topic ('/camera/rgb/image_raw' for
        simulated run and '/raspicam_node/image/compressed' for real
        world run.
        """
        if self.work_mode == 'simulation':
            # Select bgr8 because its the OpenCV encoding by default
            img_raw = self.bridge_object.imgmsg_to_cv2(
                image, desired_encoding="bgr8"
            )
        else:
            cv_np_arr = np.frombuffer(image.data, np.uint8)
            img_raw = cv2.imdecode(cv_np_arr, cv2.IMREAD_COLOR)

        # Init stop sign
        stop_sign = []

        # Detect
        gray_image = cv2.cvtColor(img_raw, cv2.COLOR_BGR2GRAY)
        stop_sign = self.stop_sign_classifier.detectMultiScale(
            gray_image, 1.2, 5,
            maxSize=(120, 120)
        )

        if len(stop_sign) != 0:
            stop_sign = list(stop_sign[0])

            # Update the msg
            prob = 1
            x1 = stop_sign[0]
            y1 = stop_sign[1]
            x2 = stop_sign[0] + stop_sign[2]
            y2 = stop_sign[1] + stop_sign[3]
            area = stop_sign[2] * stop_sign[3]

            # Create the msg to publish
            self.stop_sign_msg.data = [
                prob, x1, y1,
                x2, y2, area
            ]
        else:
            # Update the msg
            self.stop_sign_msg.data = []

        # Publish the data to '/stop_sign'
        self.stop_sign_pub.publish(self.stop_sign_msg)
        self.rate.sleep()


def main():
    try:
        stop_sign_detection_object = StopSignDetection(
            node_name='stop_sign_detection'
        )
        rate = rospy.Rate(10)
        ctrl_c = False

        def shutdownhook():
            # Works better than rospy.is_shutdown()
            rospy.loginfo("Shutdown time!")
            ctrl_c = True

        rospy.on_shutdown(shutdownhook)
        while not ctrl_c:
            rate.sleep()

    except rospy.ROSInterruptException:
        pass

if __name__ == '__main__':
    main()
