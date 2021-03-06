#!/usr/bin/env python3
import cv2
import numpy as np
import rospy
from cv_bridge import CvBridge
from sensor_msgs.msg import Image
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import Float32MultiArray

from PID_controller import PID

# Use LAB color space values to generate mask
# If we can't differentiat we can modify the LAB color space such that we can improve differentiation in HSV color space

class LineFollower:
    def __init__(self):
        self.bridge_object = CvBridge()

        # Init the work mode (simulation or real-world)
        self.work_mode = rospy.get_param('~work_mode')

        if self.work_mode == 'simulation':
            # Subscriber which will get images from the topic 'camera/rgb/image_raw'
            self.image_sub = rospy.Subscriber(
                "/camera/rgb/image_raw", Image, self.camera_callback)
        else:
            # Subscriber which will get images from the topic '/raspicam_node/image/compressed'
            self.image_sub = rospy.Subscriber(
                "/raspicam_node/image/compressed", CompressedImage, self.camera_callback)

        # Publisher which will publish to the the topic '/line_following'
        self.line_following_pub = rospy.Publisher(
            "/line_following", Float32MultiArray, queue_size=10)

        # Init the publish rate
        self.rate = rospy.Rate(10)

        # Init the line-following message
        self.line_following_msg = Float32MultiArray()

        # Init PID controller
        Kp = rospy.get_param('~Kp')
        Ki = rospy.get_param('~Ki')
        Kd = rospy.get_param('~Kd')
        self.pid_object = PID(Kp, Ki, Kd)

        # Center shift
        self.center_shift = rospy.get_param('~line_center_shift')

        # Init the lower bound and upper bound of the specific color
        if self.work_mode == 'simulation':
            self.lower_HSV = np.array(eval(rospy.get_param('~lower_HSV')))
            self.upper_HSV = np.array(eval(rospy.get_param('~upper_HSV')))
        else:
            # for LAB parametrization
            self.lower_LAB = np.array(eval(rospy.get_param('~lower_LAB')))
            self.upper_LAB = np.array(eval(rospy.get_param('~upper_LAB')))

    def camera_callback(self, image):
        if self.work_mode == 'simulation':
            # Select bgr8 because its the OpenCV encoding by default
            img_raw = self.bridge_object.imgmsg_to_cv2(
                image, desired_encoding="bgr8")
        else:
            cv_np_arr = np.frombuffer(image.data, np.uint8)
            img_raw = cv2.imdecode(cv_np_arr, cv2.IMREAD_COLOR)

        # Crop the parts of the image we don't need
        height, width, _ = img_raw.shape
        upper_bound, lower_bound = 180, 230
        crop_img = img_raw[int(height/2) +
                           upper_bound:int(height/2) + lower_bound][:]
        
        #crop_img = (crop_img * 1.9).astype(np.uint8)
        #crop_img = np.where(crop_img > 255, 255, crop_img)

        cv2.imshow("Crop", crop_img)
        cv2.waitKey(1)

        if self.work_mode == 'simulation':
            # Convert from RGB to HSV
            hsv = cv2.cvtColor(crop_img, cv2.COLOR_BGR2HSV)
            # Threshold the HSV image to get only specific colors
            mask = cv2.inRange(hsv, self.lower_HSV, self.upper_HSV)
        else:
            # Convert from RGB to LAB
            lab = cv2.cvtColor(crop_img, cv2.COLOR_BGR2LAB)
            # Threshold the LAB image to get only specific colors
            mask = cv2.inRange(lab, self.lower_LAB, self.upper_LAB) 

        # Find the centroid
        cv2.imshow("Mask", mask)
        cv2.waitKey(1)
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

            # Update the msg
            self.line_following_msg.data = [
                cx, cy + height / 2 + upper_bound, angular_vel]
        else:
            # Update the msg
            self.line_following_msg.data = []

        # Publish
        self.line_following_pub.publish(self.line_following_msg)
        self.rate.sleep()


def main():
    rospy.init_node('line_following_node', anonymous=True)
    line_follower_object = LineFollower()
    rate = rospy.Rate(10)
    ctrl_c = False

    def shutdownhook():
        # Works better than rospy.is_shutdown()
        rospy.loginfo("Shutdown time!")
        ctrl_c = True

    rospy.on_shutdown(shutdownhook)
    while not ctrl_c:
        rate.sleep()


if __name__ == '__main__':
    main()