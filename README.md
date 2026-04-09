## Experimental-Image-Sorter
- This is a fork of Simple-Image-Sorter by Legendsmith https://github.com/Legendsmith/Simple-Image-Sorter. Code from this project may be freely added upstream.

Description:
- A tool to help organize images into folders. 

Notes:
- Always backup your data.
- Tip: You can use tools like ANTIDUPL or VDF.GUI to remove duplicates of the same images or videos.

# Requirements #
- Vips windows binaries https://github.com/libvips/libvips/releases
    - File name: vips-dev-web-8.18.zip (or newer)
    - Place the whole folder into the program folder. This structure: script_folder/vips/bin
    - The folder must include the name "vips".
- VLC (64-bit) https://get.videolan.org/vlc/3.0.21/win64/vlc-3.0.21-win64.exe
    - File name: vlc-3.0.21-win64.exe (or newer)

# Changes: #

Animation/video support, lazy loading, sorting options, custom themes, QOL updates, custom imagegrid (for smooth scrolling), many optimizations.


# Compiling #
- To compile with pyinstaller, you just do pip install pyinstaller, pyinstaller .\sortimages_multiview.py
- Then you must copy the vips binaries to the _internal folder along with "themes.json", "Plugins" (folder found in the vlc installation), "libvlc.dll" and "libvlccore.dll".
- You may omit the Plugins folder and libvlc, libvlccore if you have VLC-64 bit installed somewhere on your system.
