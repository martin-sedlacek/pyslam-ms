#!/usr/bin/env -S python3 -O
"""
* This file is part of PYSLAM 
*
* Copyright (C) 2016-present Luigi Freda <luigi dot freda at gmail dot com> 
*
* PYSLAM is free software: you can redistribute it and/or modify
* it under the terms of the GNU General Public License as published by
* the Free Software Foundation, either version 3 of the License, or
* (at your option) any later version.
*
* PYSLAM is distributed in the hope that it will be useful,
* but WITHOUT ANY WARRANTY; without even the implied warranty of
* MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
* GNU General Public License for more details.
*
* You should have received a copy of the GNU General Public License
* along with PYSLAM. If not, see <http://www.gnu.org/licenses/>.
"""

import numpy as np
import cv2
import math
import time 

import platform 

from config import Config

from slam import Slam, SlamState
from camera  import PinholeCamera
from ground_truth import groundtruth_factory
from dataset import dataset_factory

#from mplot3d import Mplot3d
#from mplot2d import Mplot2d
from mplot_thread import Mplot2d, Mplot3d

if platform.system()  == 'Linux':     
    from display2D import Display2D  #  !NOTE: pygame generate troubles under macOS!

from viewer3D import Viewer3D
from utils_sys import getchar, Printer 

from feature_tracker import feature_tracker_factory, FeatureTrackerTypes 
from feature_manager import feature_manager_factory
from feature_types import FeatureDetectorTypes, FeatureDescriptorTypes, FeatureInfo
from feature_matcher import FeatureMatcherTypes

from feature_tracker_configs import FeatureTrackerConfigs

from parameters import Parameters  
import multiprocessing as mp 


if __name__ == "__main__":

    config = Config()

    dataset = dataset_factory(config.dataset_settings)

    #groundtruth = groundtruth_factory(config.dataset_settings)
    groundtruth = None # not actually used by Slam() class; could be used for evaluating performances

    cam = PinholeCamera(config.cam_settings['Camera.width'], config.cam_settings['Camera.height'],
                        config.cam_settings['Camera.fx'], config.cam_settings['Camera.fy'],
                        config.cam_settings['Camera.cx'], config.cam_settings['Camera.cy'],
                        config.DistCoef, config.cam_settings['Camera.fps'])
    
    num_features=2000 

    tracker_type = FeatureTrackerTypes.DES_BF      # descriptor-based, brute force matching with knn 
    #tracker_type = FeatureTrackerTypes.DES_FLANN  # descriptor-based, FLANN-based matching 

    # select your tracker configuration (see the file feature_tracker_configs.py) 
    # FeatureTrackerConfigs: SHI_TOMASI_ORB, FAST_ORB, ORB, ORB2, ORB2_FREAK, ORB2_BEBLID, BRISK, AKAZE, FAST_FREAK, SIFT, ROOT_SIFT, SURF, SUPERPOINT, FAST_TFEAT, CONTEXTDESC, LIGHTGLUE, XFEAT, XFEAT_XFEAT
    # WARNING: At present, SLAM is not able to support LOFTR and other "pure" image matchers (further details in the commenting notes of LOFTR in feature_tracker_configs.py).
    tracker_config = FeatureTrackerConfigs.TEST
    tracker_config['num_features'] = num_features
    tracker_config['tracker_type'] = tracker_type
    
    print('tracker_config: ',tracker_config)    
    feature_tracker = feature_tracker_factory(**tracker_config)
    
    # create SLAM object 
    slam = Slam(cam, feature_tracker, groundtruth)
    time.sleep(1) # to show initial messages 

    viewer3D = Viewer3D()
    
    if platform.system()  == 'Linux':    
        display2d = Display2D(cam.width, cam.height)  # pygame interface 
    else: 
        display2d = None  # enable this if you want to use opencv window

    matched_points_plt = Mplot2d(xlabel='img id', ylabel='# matches',title='# matches')    

    do_step = False   
    is_paused = False

    gt_xyz = []
    with open("/home/vy/datasets/scannet/scans/scene0000_00/tmp_img_martin/ground_truth.txt", 'r') as file:
        for line in file:
            x, y, z, _ = map(float, line.split())
            gt_xyz.append((x, y, z))

    img_id = 0  #180, 340, 400   # you can start from a desired frame id if needed 
    while dataset.isOk():
            
        if not is_paused: 
            print('..................................')
            print('image: ', img_id)                
            img = dataset.getImageColor(img_id)
            if img is None:
                print('image is empty')
                getchar()
            timestamp = dataset.getTimestamp()          # get current timestamp 
            next_timestamp = dataset.getNextTimestamp() # get next timestamp 
            frame_duration = next_timestamp-timestamp 

            if img is not None:
                time_start = time.time()                  
                slam.track(img, img_id, timestamp)  # main SLAM function 
                print(slam.tracking.tracking_history.relative_frame_poses)

                # 3D display (map display)
                if viewer3D is not None:
                    viewer3D.draw_map(slam)

                img_draw = slam.map.draw_feature_trails(img)

                # --------------------------------------------------------------
                is_draw_traj_img = True
                traj_img_size = 800
                traj_img = np.zeros((traj_img_size, traj_img_size, 3), dtype=np.uint8)
                half_traj_img_size = int(0.5 * traj_img_size)
                draw_scale = 1

                if is_draw_traj_img:      # draw 2D trajectory (on the plane xz)
                    #x, y, z = vo.traj3d_est[-1]
                    x, y, z = slam.tracking.tracking_history.relative_frame_poses[-1]
                    #x_true, y_true, z_true = vo.traj3d_gt[-1]
                    x_true, y_true, z_true = gt_xyz[img_id]

                    draw_x, draw_y = int(draw_scale*x) + half_traj_img_size, half_traj_img_size - int(draw_scale*z)
                    true_x, true_y = int(draw_scale*x_true) + half_traj_img_size, half_traj_img_size - int(draw_scale*z_true)
                    cv2.circle(traj_img, (draw_x, draw_y), 1,(img_id*255/4540, 255-img_id*255/4540, 0), 1)   # estimated from green to blue
                    cv2.circle(traj_img, (true_x, true_y), 1,(0, 0, 255), 1)  # groundtruth in red
                    # write text on traj_img
                    cv2.rectangle(traj_img, (10, 20), (600, 60), (0, 0, 0), -1)
                    text = "Coordinates: x=%2fm y=%2fm z=%2fm" % (x, y, z)
                    cv2.putText(traj_img, text, (20, 40), cv2.FONT_HERSHEY_PLAIN, 1, (255, 255, 255), 1, 8)
                    # show
                    cv2.imwrite('/home/vy/projects/lv_slam_martin/pyslam-ms/path_plot.png', traj_img)
                # --------------------------------------------------------------

                # 2D display (image display)
                if display2d is not None:
                    display2d.draw(img_draw)
                else: 
                    cv2.imshow('Camera', img_draw)

                if matched_points_plt is not None: 
                    if slam.tracking.num_matched_kps is not None: 
                        matched_kps_signal = [img_id, slam.tracking.num_matched_kps]     
                        matched_points_plt.draw(matched_kps_signal,'# keypoint matches',color='r')                         
                    if slam.tracking.num_inliers is not None: 
                        inliers_signal = [img_id, slam.tracking.num_inliers]                    
                        matched_points_plt.draw(inliers_signal,'# inliers',color='g')
                    if slam.tracking.num_matched_map_points is not None: 
                        valid_matched_map_points_signal = [img_id, slam.tracking.num_matched_map_points]   # valid matched map points (in current pose optimization)                                       
                        matched_points_plt.draw(valid_matched_map_points_signal,'# matched map pts', color='b')  
                    if slam.tracking.num_kf_ref_tracked_points is not None: 
                        kf_ref_tracked_points_signal = [img_id, slam.tracking.num_kf_ref_tracked_points]                    
                        matched_points_plt.draw(kf_ref_tracked_points_signal,'# $KF_{ref}$  tracked pts',color='c')   
                    if slam.tracking.descriptor_distance_sigma is not None: 
                        descriptor_sigma_signal = [img_id, slam.tracking.descriptor_distance_sigma]                    
                        matched_points_plt.draw(descriptor_sigma_signal,'descriptor distance $\sigma_{th}$',color='k')                                                                 
                    matched_points_plt.refresh()    
                
                duration = time.time()-time_start 
                if(frame_duration > duration):
                    print('sleeping for frame')
                    time.sleep(frame_duration-duration)        
                    
            img_id += 1  
        else:
            time.sleep(1)                                 
        
        # get keys 
        key = matched_points_plt.get_key()  
        key_cv = cv2.waitKey(1) & 0xFF    
        
        # manage interface infos  
        
        if slam.tracking.state==SlamState.LOST:
            #if display2d is not None:
            #    getchar()
            #else:
            key_cv = cv2.waitKey(0) & 0xFF   # useful when drawing stuff for debugging
         
        if do_step and img_id > 1:
            # stop at each frame
            #if display2d is not None:
            #    getchar()
            #else:
            key_cv = cv2.waitKey(0) & 0xFF
        
        if key == 'd' or (key_cv == ord('d')):
            do_step = not do_step  
            Printer.green('do step: ', do_step) 
                      
        if key == 'q' or (key_cv == ord('q')):
            if display2d is not None:
                display2d.quit()
            if viewer3D is not None:
                viewer3D.quit()
            if matched_points_plt is not None:
                matched_points_plt.quit()
            break
        
        if viewer3D is not None:
            is_paused = not viewer3D.is_paused()         

    slam.quit()
    
    cv2.waitKey(0)
    cv2.destroyAllWindows()
