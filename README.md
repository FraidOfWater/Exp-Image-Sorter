# Simple-Image-Sorter Fork
This is a fork of Simple-Image-Sorter by Legendsmith https://github.com/Legendsmith/Simple-Image-Sorter. If author reads this, feel free to merge this?

# Sorts images into destinations #
This fork is a hobby, it adds new features and other tweaks, and removes some others. Light experimenting with threading and optimization. Tried to make it very customizable! Now supports animations!

# Changelog: #

      GUI Enhancements

    Sorting Options: Added "Sort by date modified" in GUI and Prefs.json.
    View Options: Introduced an option box to show unassigned, assigned, moved, or animations.
    Docked Image Viewer: Choose between integrated or free-floating viewer.
    Auto Next: Automatically shows the next image upon assigning the current one.
    Single View Assigning: Assign images directly from the viewer with a hotkey.
    Name Truncation: Prevents overflow and misalignment in the grid / fixed root problem auto resizing gridboxes..
    Transient Windows: Windows spawned by the main GUI now stay on top.
    File Format Support: Added support for .gif and .webp and .mp4 (thumbnails only). (not released yet, build from latest source)
    Navigator: Use arrow keys or WASD to navigate the grid; lock images for zooming with enter or clicking. Press Spacebar to check images.
    Theme Customization: Main theme is now "Midnight Blue"; customize using hex codes; prefs.json.
    Window Position Saving: Remembers user-adjusted positions and sizes.
    Scrollbar Override: Option to disable the white scrollbar.

      Performance Improvements

    Image Header Hashing: Faster image loading by reading headers instead of full binary data.
    Overwrite Safeguards: Prevents overwriting locked images or those assigned to others.
    Threading: Implements threading for lazy loading of images and GIFs/WebPs.
    Buffering: Buffers large images to reduce latency; configurable in Prefs.json.

      Image Viewer Enhancements

    Auto Scaling and Centering: Images automatically scale and center within the viewer.
    Centering Options: Customize centering behavior.
    Free Zooming: Zoom functionality no longer requires hovering over the image.

      Miscellaneous

    Run Without Compiling: Copy over required DLLs and run the script directly.
    User File Accessibility: Prefs, session data, and data folders are now outside _internal
    Core Utilization: Automatically utilizes available CPU cores.
    Fixed Bugs: That appeared in the original
    

# Warnings #

    Use tools like ANTIDUPL to remove duplicates.
    No guarantees of functionality; backup images before use.
    GIFs and WebPs do not support zooming due to implementation complexity.
    Image renaming and dupe checking removed/not supported.

# Requirements For Building #
### How to Build ###

1. Install Python: Ensure you have Python installed.
2. Install Dependencies: Use pip to install the required dependencies:

       pip install pyvips tkinter-tooltip pillow pyinstaller (more now check install.bat, also need vlc.exe 64bit)
         or if you built yourself from the latest source (mp4, webm animation and audio support) "pip install pyvips tkinter-tooltip pillow pyinstaller opencv-python audioop-lts imageio imageio[ffmpeg] pydub pygame simpleaudio"

4. Required DLLs: Obtain the following DLLs from a compiled copy in the _internal folder:

       libglib-2.0
       libgobject-2.0
       libvips-42
       libvips-cpp-42

      Place the DLLs in the same folder as the .py and .bat scripts.

5. Run the Batch File: Execute the .bat file.

      The finished copy can be found in the dist folder.

      Note: If you edit any source files, delete the build and dist folders to avoid building from outdated files.

      You can also add --noconsole and --onefile to the pyinstaller command to disable the console or to avoid having the _internal folder.

      If you get any errors, try restarting the computer, run the .exe with cmd so you see any errors. Ask chatGPT!

# How to run as a script #
### Running Without Building ###

   1. Edit sortimages_multiview.py and enable the following code block, then save:

            #""" # This can/should be commented if you build.
            import ctypes
            try:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                dll_path1 = os.path.join(script_dir, 'libvips-cpp-42.dll')
                dll_path2 = os.path.join(script_dir, 'libvips-42.dll')
                dll_path3 = os.path.join(script_dir, 'libglib-2.0-0.dll')
                dll_path4 = os.path.join(script_dir, 'libgobject-2.0-0.dll')
            except FileNotFoundError:
                logging
            ctypes.CDLL(dll_path1)
            ctypes.CDLL(dll_path2)
            ctypes.CDLL(dll_path3)
            ctypes.CDLL(dll_path4)
            #"""
   2. Shortcut
      
            start.bat
                  cd %~dp0
                  python sortimages_multiview.py
                  pause
   3. Note

            To edit this in VSC, you must open the FOLDER with "Open with code". Opening only the sortimages_multiview.py will make VSC's terminal use \Users\user path,which will fail to import pyvips for some reason.
      
      
End of file congratz!
