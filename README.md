## Experimental-Image-Sorter
Description:
- Helps organize imagesets by sorting images into folders. This fork builds on the original by adding various features (see changelog).

Scenario:
- Are you sorting images to specific folders via windows file-manager? Well no more, this program lets you preview images, animations and videos, and move them to preset folders using only your keyboard.

This is a fork of Simple-Image-Sorter by Legendsmith https://github.com/Legendsmith/Simple-Image-Sorter. Code from this project may freely be added upstream.

# Changes: #

      FEATURES

    Theme Customization: Main theme is now "Midnight Blue"; customize using hex codes; themes.json. (Can also add your own, themes.json is parsed on each run, and themes added to options)
    Animation support: Added support for .gif, .webp, .webm and .mp4.
    Docked Image Viewer: Choose between integrated or free-floating viewer.

    Navigation: Use arrow keys to navigate the grid.
    Show Next: Automatically shows the next image upon assigning the current one.
    Quick Assigning: Assign images directly from the viewer with a hotkey.
    Auto Load: Load more images up to a value, if below that value.

    Sorting Options: Added "Sort by date modified"-button.
    View Options: Introduced an option box to show unassigned, assigned, moved, or animations.

    Transient Windows: Windows spawned by the main GUI now stay on top (consistency).
    Window Position Saving: Find it just how you left it.
    Scrollbar Override: Option to disable the white scrollbar.

    Removed: Dupechecking (It confused me, haha!)

      PERFORMANCE

    Image Header Hashing: Faster image loading by reading headers instead of full binary data.
    Threading: Implements threading for lazy loading of images and GIFs/WebPs.
    Buffering: Buffers large images to reduce latency; configurable in Prefs.json.

    

# Warnings & Other info #

    Use tools like ANTIDUPL to remove duplicates.
    No guarantees of functionality; backup images before use. Largely untested for now.
    GIFs, WebPs, webm and mp4 do not support zooming due to implementation complexity.

How do I run it?
- Download a compiled copy from releases. There are two versions: 1. Executable, 2. Script.
- The executable acts as a standalone and you don't need anything else!
- The script requires you to install python (latest), run install.bat (install dependencies), install vlc (64-bit via installer), and to run start.bat.

How do I compile from source?

- Vips windows binaries:
            Can be found on github: https://github.com/libvips/libvips/releases
            File name: vips-dev-w64-web-8.16.0.zip (or newer)
            Place the whole folder into the program folder. This structure: SIME/vips/bin
- VLC files (64-bit):
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
            Run install.bat
            Include vips windows binaries.
            Install VLC 64-bit on your system or include the VLC files.

To do:

      Do some testing.
      Do some polish. Ensure stability
      Change this README to a GUIDE on all the features, much like author's version.

On pushes upstream:

      I fear pushing upstream. I rewrote so much on my way, perhaps it is best as a separate fork altogether.
      Or perhaps we will move this to a new branch upstream.

Considerations:

      This fork removes dupechecking and may not support linux inputs.
      
End of file congratz!
