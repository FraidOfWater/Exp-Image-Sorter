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
<details>
  <summary>Main changes in this fork:</summary>

> QOL:
> - Can reveal images in file-explorer.
> - Sort orders. + natsort for logical filename orders. Filename++ separates one word hex codes, just numbers and actual filenames into groups.
> - Animation/video support.
> - A Search functionality to sort into deeply nested folder structures.
> - Navigation using arrow keys or mouse wheel (with caps-lock).
> - If source and destination roots are same, we don't search images recursively.
> - Quick assigning and navigation via caps-lock + Scroll, and then Enter to quicky assign to the selected destination. The highlighted item can also be quickly assigned without "marking" it first via hotkey.
> 
> GUI changes:
> - Window positions are saved across runs.
> - Folders can be dragged to a better order.
> - Destination hotkeys can be reassigned using Middle-Mouse + key.
> - Embedded + standalone image viewer, side can be changed.
> - Customizable themes
> 
> Performance changes:
> - Threaded thumbnail generation
> - Viewer with many optimizations like precaching.
> - Deferred module loading for fast startup.
> - Custom imagegrid to avoid tkinter artifacts.

</details>

# Compiling #
- To compile with pyinstaller, you just do pip install pyinstaller, pyinstaller .\sortimages_multiview.py
- Then you must copy the vips binaries to the _internal folder along with "themes.json", "Plugins" (folder found in the vlc installation), "libvlc.dll" and "libvlccore.dll".
- You may omit the Plugins folder and libvlc, libvlccore if you have VLC-64 bit installed somewhere on your system.
