# Copyright (c) 2025 Stephen G. Pope
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import os
import subprocess
import logging
import random
from services.file_management import download_file
from PIL import Image
from config import LOCAL_STORAGE_PATH

logger = logging.getLogger(__name__)


def process_image_to_video(image_url, length, frame_rate, zoom_speed, job_id, webhook_url=None):
    # ==== EFFECT CONTROL VARIABLES ====
    
    # Shake Effect Settings
    SHAKE_INTENSITY = 8        # 1-2: subtle, 3-5: noticeable, 6+: dramatic, 8+: very visible
    SHAKE_FREQUENCY_X = 0.15   # Lower = slower horizontal shake, higher = faster
    SHAKE_FREQUENCY_Y = 0.18   # Lower = slower vertical shake, higher = faster
    SHAKE_BORDER = 20          # Border pixels to allow for shake movement (should be > shake_intensity)
    
    # Movement Pattern Settings
    MOVEMENT_SPEED_MULTIPLIER = 1.0  # 0.5: slower movements, 1.0: normal, 2.0: faster movements
    ENABLE_CENTER_ZOOM = False       # *** DISABLED CENTER ZOOM ***
    ENABLE_LINEAR_PANS = True        # Include left-right, top-bottom pans
    ENABLE_DIAGONAL_PANS = True      # Include diagonal movements
    
    # Quality Settings
    UPSCALE_QUALITY_BOOST = True     # Use higher resolution scaling for better quality
    CUSTOM_SCALE_MULTIPLIER = 1.0    # Adjust base scaling (1.0 = default, 1.5 = higher quality)
    
    # Debug Settings
    LOG_MOVEMENT_PATTERN = True      # Log which movement pattern was selected
    LOG_SHAKE_DETAILS = True         # Log shake filter details
    
    # ==== INTERNAL FUNCTIONS ====
    
    def get_movement_pattern(total_frames):
        """Returns random x,y expressions for different movement patterns"""
        
        patterns = {}
        speed_factor = f"*{MOVEMENT_SPEED_MULTIPLIER}" if MOVEMENT_SPEED_MULTIPLIER != 1.0 else ""
        
        # Linear movement patterns
        if ENABLE_LINEAR_PANS:
            patterns.update({
                'left_to_right': {
                    'x': f"(iw-iw/zoom)*on/{total_frames}{speed_factor}",
                    'y': "ih/2-(ih/zoom/2)",
                    'name': "Left to Right Pan"
                },
                'right_to_left': {
                    'x': f"(iw-iw/zoom)*(1-on/{total_frames}{speed_factor})",
                    'y': "ih/2-(ih/zoom/2)",
                    'name': "Right to Left Pan"
                },
                'top_to_bottom': {
                    'x': "iw/2-(iw/zoom/2)",
                    'y': f"(ih-ih/zoom)*on/{total_frames}{speed_factor}",
                    'name': "Top to Bottom Pan"
                },
                'bottom_to_top': {
                    'x': "iw/2-(iw/zoom/2)",
                    'y': f"(ih-ih/zoom)*(1-on/{total_frames}{speed_factor})",
                    'name': "Bottom to Top Pan"
                }
            })
        
        # Diagonal movement patterns
        if ENABLE_DIAGONAL_PANS:
            patterns.update({
                'diagonal_up': {
                    'x': f"(iw-iw/zoom)*on/{total_frames}{speed_factor}",
                    'y': f"(ih-ih/zoom)*(1-on/{total_frames}{speed_factor})",
                    'name': "Diagonal Up (Bottom-Left to Top-Right)"
                },
                'diagonal_down': {
                    'x': f"(iw-iw/zoom)*on/{total_frames}{speed_factor}",
                    'y': f"(ih-ih/zoom)*on/{total_frames}{speed_factor}",
                    'name': "Diagonal Down (Top-Left to Bottom-Right)"
                },
                'diagonal_up_reverse': {
                    'x': f"(iw-iw/zoom)*(1-on/{total_frames}{speed_factor})",
                    'y': f"(ih-ih/zoom)*on/{total_frames}{speed_factor}",
                    'name': "Diagonal Up Reverse (Top-Right to Bottom-Left)"
                },
                'diagonal_down_reverse': {
                    'x': f"(iw-iw/zoom)*(1-on/{total_frames}{speed_factor})",
                    'y': f"(ih-ih/zoom)*(1-on/{total_frames}{speed_factor})",
                    'name': "Diagonal Down Reverse (Bottom-Right to Top-Left)"
                }
            })
        
        if not patterns:
            # Fallback to left-to-right if all patterns are disabled
            patterns['left_to_right'] = {
                'x': f"(iw-iw/zoom)*on/{total_frames}",
                'y': "ih/2-(ih/zoom/2)",
                'name': "Left to Right Pan (Fallback)"
            }
        
        pattern_key = random.choice(list(patterns.keys()))
        return patterns[pattern_key], pattern_key

    # ==== MAIN PROCESSING LOGIC ====
    
    try:
        # Download the image file
        image_path = download_file(image_url, LOCAL_STORAGE_PATH)
        logger.info(f"Downloaded image to {image_path}")

        # Get image dimensions using Pillow
        with Image.open(image_path) as img:
            width, height = img.size
        logger.info(f"Original image dimensions: {width}x{height}")

        # Prepare the output path
        output_path = os.path.join(LOCAL_STORAGE_PATH, f"{job_id}.mp4")

        # Determine orientation and set appropriate dimensions
        if width > height:
            # Landscape orientation
            if UPSCALE_QUALITY_BOOST:
                base_scale_w = int(7680 * CUSTOM_SCALE_MULTIPLIER)
                base_scale_h = int(4320 * CUSTOM_SCALE_MULTIPLIER)
                scale_dims = f"{base_scale_w}:{base_scale_h}"
            else:
                scale_dims = "7680:4320"
            output_dims = "1920x1080"
        else:
            # Portrait orientation
            if UPSCALE_QUALITY_BOOST:
                base_scale_w = int(4320 * CUSTOM_SCALE_MULTIPLIER)
                base_scale_h = int(7680 * CUSTOM_SCALE_MULTIPLIER)
                scale_dims = f"{base_scale_w}:{base_scale_h}"
            else:
                scale_dims = "4320:7680"
            output_dims = "1080x1920"

        # Calculate total frames and zoom factor
        total_frames = int(length * frame_rate)
        zoom_factor = 1 + (zoom_speed * length)

        # Get random movement pattern
        movement, pattern_name = get_movement_pattern(total_frames)
        x_expr = movement['x']
        y_expr = movement['y']

        # Build enhanced shake filter
        shake_filter = ""
        if SHAKE_INTENSITY > 0:
            shake_crop_w = SHAKE_BORDER * 2
            shake_crop_h = SHAKE_BORDER * 2
            shake_x = f"{SHAKE_BORDER}+{SHAKE_INTENSITY}*sin(n*{SHAKE_FREQUENCY_X})"
            shake_y = f"{SHAKE_BORDER}+{SHAKE_INTENSITY}*cos(n*{SHAKE_FREQUENCY_Y})"
            shake_filter = f",crop=iw-{shake_crop_w}:ih-{shake_crop_h}:{shake_x}:{shake_y}"

        logger.info(f"Using scale dimensions: {scale_dims}, output dimensions: {output_dims}")
        logger.info(f"Video length: {length}s, Frame rate: {frame_rate}fps, Total frames: {total_frames}")
        logger.info(f"Zoom speed: {zoom_speed}/s, Final zoom factor: {zoom_factor}")
        logger.info(f"Shake intensity: {SHAKE_INTENSITY}, Movement speed: {MOVEMENT_SPEED_MULTIPLIER}x")
        
        if LOG_MOVEMENT_PATTERN:
            logger.info(f"Movement pattern selected: {movement['name']}")
        
        if LOG_SHAKE_DETAILS and SHAKE_INTENSITY > 0:
            logger.info(f"Shake filter: crop=iw-{shake_crop_w}:ih-{shake_crop_h}:{shake_x}:{shake_y}")

        # Prepare FFmpeg command with all effects, maintaining your fps filter and -r parameter
        video_filter = f"scale={scale_dims},zoompan=z='min(1+({zoom_speed}*{length})*on/{total_frames}, {zoom_factor})':d={total_frames}:x='{x_expr}':y='{y_expr}':s={output_dims}{shake_filter},fps={frame_rate}"
        
        cmd = [
            'ffmpeg', '-framerate', str(frame_rate), '-loop', '1', '-i', image_path,
            '-vf', video_filter,
            '-c:v', 'libx264', '-r', str(frame_rate), '-t', str(length), '-pix_fmt', 'yuv420p', output_path
        ]

        logger.info(f"Running FFmpeg command: {' '.join(cmd)}")

        # Run FFmpeg command
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"FFmpeg command failed. Error: {result.stderr}")
            raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)

        logger.info(f"Video created successfully: {output_path}")

        # Clean up input file
        os.remove(image_path)

        return output_path
        
    except Exception as e:
        logger.error(f"Error in process_image_to_video: {str(e)}", exc_info=True)
        raise
