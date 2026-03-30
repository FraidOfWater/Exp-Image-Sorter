import winreg
import ctypes
import sys
import os

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def delete_key_recursive(root, path):
    """
    Standard winreg.DeleteKey fails if a key has subkeys.
    This helper clears children before deleting the parent.
    """
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_ALL_ACCESS) as key:
            while True:
                try:
                    # Always check the first subkey (index 0)
                    sub_key_name = winreg.EnumKey(key, 0)
                    delete_key_recursive(root, f"{path}\\{sub_key_name}")
                except OSError:
                    # No more subkeys
                    break
        winreg.DeleteKey(root, path)
    except FileNotFoundError:
        pass # Already gone

def remove_from_context_menu(menu_name):
    locations = [
        rf"Directory\shell\{menu_name}",           # Folder Icon
        rf"Directory\Background\shell\{menu_name}" # Folder Background
    ]
    
    found_any = False
    for path in locations:
        try:
            # Check if key exists
            winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, path)
            delete_key_recursive(winreg.HKEY_CLASSES_ROOT, path)
            print(f"Successfully deleted: HKEY_CLASSES_ROOT\\{path}")
            found_any = True
        except FileNotFoundError:
            continue
            
    if not found_any:
        print(f"No context menu items found for '{menu_name}'.")

if __name__ == "__main__":
    if is_admin():
        MENU_NAME = "Open with ThumbManager"
        remove_from_context_menu(MENU_NAME)
        
        print("\nCleanup complete.")
        input("Press Enter to exit...")
    else:
        # --- ELEVATION ---
        print("Requesting Admin privileges for cleanup...")
        script = os.path.abspath(sys.argv[0])
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}"', None, 1)
        sys.exit()