# Simple-Image-Sorter Fork
This is a fork of Simple-Image-Sorter by Legendsmith https://github.com/Legendsmith/Simple-Image-Sorter. ~~If author reads this, feel free to merge this?~~ 

To do:
1. Do some testing.
2. Offer final compiled version of this fork to author's releases page.

# Sorts images into destinations #
This fork is a hobby, it adds new features and other tweaks, and removes some others. Light experimenting with threading and optimization. Tried to make it very customizable! Now supports animations!

# Changelog: #

      GUI

    Theme Customization: Main theme is now "Midnight Blue"; customize using hex codes; themes.json. (Can also add your own, themes.json is parsed on each run, and themes added to options)
    Animation support: Added support for .gif, .webp, .webm and .mp4.
    Docked Image Viewer: Choose between integrated or free-floating viewer.

    Navigation: Use arrow keys to navigate the grid.
    Quick Assigning: Assign images directly from the viewer with a hotkey.
    Show Next: Automatically shows the next image upon assigning the current one.
    Auto Load: Load more images up to a value, if below that value.

    Sorting Options: Added "Sort by date modified"-button.
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
    Memory limit: Due to memory requirements of animations, limit number of frames loaded to memory.
    Animation queue: Loads animations as the memory limit allows.
    Removed: Dupechecking

      IMG-VIEWER

    Auto Scaling and Centering: Images automatically scale and center within the viewer.
    Centering Options: Customize centering behavior. (untested)
    Free Zooming: Zoom functionality no longer requires hovering over the image.

# Warnings #

    Use tools like ANTIDUPL to remove duplicates.
    No guarantees of functionality; backup images before use. Largely untested for now.
    GIFs, WebPs, webm and mp4 do not support zooming due to implementation complexity.

# How to run code #
Download a compiled copy from releases.
 - Executable:
   
        Contains all dependencies.
 - Scripts:
   
       Install python, pip. Run install.bat, run start.bat.
How to compile:

      Vips windows binaries:
            Can be found on github: https://github.com/libvips/libvips/releases
            File name: vips-dev-w64-web-8.16.0.zip (or newer)
            Place the whole folder into the program folder. This structure: SIME/vips/bin
      VLC files (64-bit):
            Can be found on the web: https://get.videolan.org/vlc/3.0.21/win64/vlc-3.0.21-win64.exe
            File name: vlc-3.0.21-win64.exe (or newer)
            Place following files and folders into the program folder.
            "Plugins", libvlc.dll, libvlccore.dll.

      To compile a standalone version (EXE):
            Include vips windows binaries.
            Include VLC files.
            Run build.bat, executable will be in dist folder.

      To compile executable without vlc:
            Include vips windows binaries.
            Install VLC 64-bit on your system.
            Run build.bat, executable will be in dist folder.

      To get the script working on your own:
            Include vips windows binaries.
            Install VLC 64-bit on your system or include the VLC files.
            
       - (Note, you must run install.bat for script builds, you can then run by clicking on start.bat)
      
 Create Shortcut / Use shortcut
      
            start.bat
                  cd %~dp0
                  python sortimages_multiview.py
                  pause
Note

            To edit and run the source files in VSC, you must open the FOLDER with "Open with code". Opening only sortimages_multiview.py will make VSC's terminal use \Users\user path, which will fail to run the program. You must run from the right environment, the program folder.
      
      
End of file congratz!
