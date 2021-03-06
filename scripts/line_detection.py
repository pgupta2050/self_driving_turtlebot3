#!/usr/bin/env python3

# Import libraries
import cv2
import numpy as np
import rospy

from cv_bridge import CvBridge
from sensor_msgs.msg import Image, CompressedImage
from std_msgs.msg import Float32MultiArray
from pid_controller import PID


class LineFollower:
    """
    Line Follower class for line following
    """

    def __init__(self, node_name):
        """
        Init function for LineFollower class
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

        # Publisher to publish data for line following to
        # the topic '/line_following'
        self.line_following_pub = rospy.Publisher(
            "/line_following", Float32MultiArray, queue_size=10
        )

        # Init the publish rate
        self.rate = rospy.Rate(10)

        # Init the line-following message
        self.line_following_msg = Float32MultiArray()

        # Init PID controller
        Kp = rospy.get_param('~Kp')
        Ki = rospy.get_param('~Ki')
        Kd = rospy.get_param('~Kd')
        self.pid_object = PID(Kp, Ki, Kd)

        # Init center shift
        self.center_shift = rospy.get_param('~line_center_shift')

        # Init the lower bound and upper bound of the specific color
        self.lower_HSV = np.array(eval(rospy.get_param('~lower_HSV')))
        self.upper_HSV = np.array(eval(rospy.get_param('~upper_HSV')))


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

        # Crop the parts of the image we don't need
        height, width, _ = img_raw.shape
        upper_bound, lower_bound = 180, 230
        crop_img = img_raw[int(height/2) + \
                upper_bound:int(height/2) + lower_bound][:]
        
        # Convert from RGB to HSV
        hsv = cv2.cvtColor(crop_img, cv2.COLOR_BGR2HSV)

        # Threshold the HSV image to get only specific colors
        mask = cv2.inRange(hsv, self.lower_HSV, self.upper_HSV)

        m = cv2.moments(mask, False)
        try:
            cx, cy = int(m['m10']/m['m00']), int(m['m01']/m['m00'])
            found_blob = True
        except ZeroDivisionError:
            found_blob = False

        # PID Controller
        if found_blob:
            # Determine the angular velocity
            error = cx - width / 2 + self.center_shift
            angular_vel = self.pid_object.update(error) / 450

            # Create the msg to publish
            self.line_following_msg.data = [
                cx,
                cy + height / 2 + upper_bound,
                angular_vel
            ]
        else:
            # Update the msg
            self.line_following_msg.data = []

        # Publish the data to '/line_following'
        self.line_following_pub.publish(self.line_following_msg)
        self.rate.sleep()


def main():
    try:
        line_follower_object = LineFollower(
            node_name='line_following_node'
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
