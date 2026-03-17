## Experimental-Image-Sorter
Description:
- Helps organize imagesets by sorting images into folders. This fork builds on the original by adding various features (see changelog).

Scenario:
- Are you sorting images to specific folders via windows file-manager? Well no more, this program lets you preview images, animations and videos, and move them to preset folders using only your keyboard.

This is a fork of Simple-Image-Sorter by Legendsmith https://github.com/Legendsmith/Simple-Image-Sorter. Code from this project may be freely added upstream.

# Changes: #

# Warnings & Other info #

    Use tools like ANTIDUPL to remove duplicates.
    No guarantees of functionality; backup images before use. Largely untested for now. I use this myself, but I do have a backup in case I messed up somewhere in the code.

How do I run it?
- Download a compiled copy from releases. There are two versions: 1. Executable, 2. Script.
- The executable acts as a standalone and you don't need anything else!
- The script requires you to install python (latest), run install.bat (install dependencies), install vlc (64-bit via installer), and to run start.bat.

How do I compile from source?

- Vips windows binaries:
            Can be found on github: https://github.com/libvips/libvips/releases
            File name: vips-dev-web-8.18.zip (or newer)
            Place the whole folder into the program folder. This structure: SIME/vips/bin
            You may need to rename it to vips-dev-8.18, so the scripts can find it.
- VLC files (64-bit):
            Can be found on the web: https://get.videolan.org/vlc/3.0.21/win64/vlc-3.0.21-win64.exe
            File name: vlc-3.0.21-win64.exe (or newer)
            Place following files and folders into the program folder.
            "Plugins", libvlc.dll, libvlccore.dll.

      To compile a standalone version (EXE):
            Complile using pyinstaller, include imageio hidden metadata. You must have all python modules imported.
              pyinstaller .\sortimages_multiview.py --copy-metadata=imageio
            Copy vips windows binaries into the internal folder.
            Copy VLC files into the internal folder. (You don't need these if vlc is installed somewhere on the system)

      To get the script working on your own:
            Run install.bat
            Include vips windows binaries.
            Install VLC 64-bit on your system or include the VLC files.

Considerations:

      This fork is written on windows, and doesn't consider things like linux key bindings.
      
End of file congratz!
