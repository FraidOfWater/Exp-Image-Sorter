import ctypes
import sys
import os
import winreg

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def add_to_context_menu(menu_name, script_path):
    python_exe = sys.executable.replace("python.exe", "pythonw.exe")
    
    # %1 is used for folder icons, %V is used for backgrounds. 
    # Using "%1" (or "%V") in quotes handles paths with spaces.
    cmd_folder = f'"{python_exe}" "{script_path}" -quick "%1"'
    cmd_bg     = f'"{python_exe}" "{script_path}" -quick "%V"'
    
    # The two locations in the registry
    locations = [
        (rf"Directory\shell\{menu_name}", cmd_folder),           # Right-click FOLDER ICON
        (rf"Directory\Background\shell\{menu_name}", cmd_bg)     # Right-click EMPTY SPACE
    ]
    
    for key_path, command in locations:
        try:
            # Create main key
            with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, key_path) as key:
                winreg.SetValue(key, "", winreg.REG_SZ, menu_name)
                winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, sys.executable)
                
                # or .ico file
                # icon_path = 
                # winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, icon_path)

            # Create command subkey
            with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, rf"{key_path}\command") as key:
                winreg.SetValue(key, "", winreg.REG_SZ, command)
                
            print(f"Successfully added to: {key_path}")
        except Exception as e:
            print(f"Failed to write to {key_path}: {e}")

if __name__ == "__main__":
    if is_admin():
        MY_SCRIPT = r"C:\path\to\your\copy\Exp-Img-Sorter\main\sortimages_multiview.py"
        
        if not os.path.exists(MY_SCRIPT):
            print(f"ERROR: Script not found at {MY_SCRIPT}")
        else:
            add_to_context_menu("Open with ThumbManager", MY_SCRIPT)
            
        print("\nAll operations complete.")
        input("Press Enter to close...") 
    else:
        # Rerun the script with admin rights
        script = os.path.abspath(sys.argv[0])
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}"', None, 1)
        sys.exit()