# Simple-Image-Sorter Fork
This is a fork of Simple-Image-Sorter by Legendsmith https://github.com/Legendsmith/Simple-Image-Sorter. If author reads this, feel free to merge this?

# Sorts images into destinations #
This fork is a hobby, it adds new features and other tweaks, and removes some others. Light experimenting with threading and optimization. Tried to make it very customizable! Now supports animations!

# Changelog: #

      GUI

    Theme Customization: Main theme is now "Midnight Blue"; customize using hex codes; prefs.json.
    Animation support: Added support for .gif, .webp, .webm and .mp4.
    Docked Image Viewer: Choose between integrated or free-floating viewer.

    Navigation: Use arrow keys or WASD to navigate the grid; lock images for zooming with enter or clicking. Press Spacebar to check images.
    Quick Assigning: Assign images directly from the viewer with a hotkey.
    Show Next: Automatically shows the next image upon assigning the current one.

    Sorting Options: Added "Sort by date modified" in GUI and Prefs.json.
    View Options: Introduced an option box to show unassigned, assigned, moved, or animations.
    Name Truncation: Prevents overflow and misalignment in the grid / fixed root problem auto resizing gridboxes..
    
    Transient Windows: Windows spawned by the main GUI now stay on top (consistency).
    Window Position Saving: Find it just how you left it.
    Scrollbar Override: Option to disable the white scrollbar.

      CORE

    Image Header Hashing: Faster image loading by reading headers instead of full binary data.
    Overwrite Safeguards: Prevents overwriting locked images or those assigned to others.
    Threading: Implements threading for lazy loading of images and GIFs/WebPs.
    Buffering: Buffers large images to reduce latency; configurable in Prefs.json.
    Removed: Dupechecking and Image-renaming

      IMG-VIEWER

    Auto Scaling and Centering: Images automatically scale and center within the viewer.
    Centering Options: Customize centering behavior. (untested)
    Free Zooming: Zoom functionality no longer requires hovering over the image.

# Warnings #

    Use tools like ANTIDUPL to remove duplicates.
    No guarantees of functionality; backup images before use.
    GIFs, WebPs, webm and mp4 do not support zooming due to implementation complexity.
    Sessions do not work for build 4.1. I will fix it in later revisions.

# How to run code #
 You can also download ready to run from releases, just install python , pip and run install.bat for dependencies.
 In releases you can download four different builds:
 - Exe.standalone (Largest)
 - Exe. (You must have vlc 64 bit installed)
 - Script.standalone
 - Script. (You must have vlc 64 bit installed) (Smallest)
 - (Note, you must run install.bat for script builds, you can then run by clicking on start.bat)

   1. Downloading requirements
      
            You need to install:
             - python (newest, 3 and above) (coded on 3.12)
             - pip (should come with python)
             - vlc (64 bit, installer)
            Then:
             - run command: pip install pillow pyvips imageio imageio[ffmpeg] python-vlc tkinter-tooltip psutil pyinstaller
             - download vips windows binaries from github: file name: "vips-dev-w64-web-8.16.0.zip" or later. https://github.com/libvips/libvips/releases. There should be a section in releases, with a link saying "WINDOWS BINARIES", if you do not see one, look for older releases with available windows binaries. (-all also works)
             - place vips: in the same folder as the .py files are in.
      
   3. Create Shortcut / Use shortcut
      
            start.bat
                  cd %~dp0
                  python sortimages_multiview.py
                  pause
   3. Note

            To edit and run the source files in VSC, you must open the FOLDER with "Open with code". Opening only sortimages_multiview.py will make VSC's terminal use \Users\user path, which will fail to run the program. You must run from the right environment, the program folder.
      
      
End of file congratz!
