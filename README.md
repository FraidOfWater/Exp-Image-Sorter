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

    Run Without Compiling: Copy over required DLLs and run the script directly. (if using newest source, must use vips-dev-xxx folder (find the link for WINDOWS BINARIES). from https://github.com/libvips/libvips/releases)) (both _w64_web (normal) and _all work)
    User File Accessibility: Prefs, session data, and data folders are now outside _internal


# Warnings #

    Use tools like ANTIDUPL to remove duplicates.
    No guarantees of functionality; backup images before use.
    GIFs and WebPs do not support zooming due to implementation complexity.
    Image renaming and dupe checking removed/not supported.

# How to "build" from source #
 You can also download ready to run from releases, just install python , pip and run install.bat for dependencies.

   1. Downloading requirements
      
            If running from newest source, you need: dependencies.
            install python (newest, 3 and above).
            install pip.
            run command: pip install pillow pyvips imageio imageio[ffmpeg] python-vlc tkinter-tooltip psutil
            download vips: Named "vips-dev-w64-web-8.16.0.zip" or later from https://github.com/libvips/libvips/releases. There should be a section and a link saying "WINDOWS BINARIES", you need that. __web and _all should both work.
            place vips: in the same folder as the .py files are in.
            download vlc: "vlc 64 bit"
            put vlc.exe: in the same folder as the .py files are in.          
      
   3. Create Shortcut
      
            start.bat
                  cd %~dp0
                  python sortimages_multiview.py
                  pause
   3. Note

            To edit this in VSC, you must open the FOLDER with "Open with code". Opening only the sortimages_multiview.py will make VSC's terminal use \Users\user path,which will fail to import pyvips for some reason.
      
      
End of file congratz!
