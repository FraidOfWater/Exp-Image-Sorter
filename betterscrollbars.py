import tkinter as tk
from tkinter import ttk

root = tk.Tk()

style = ttk.Style(root)
style.theme_use("default")

# Configure the scrollbar thumb color
style.element_create("Custom.Horizontal.Scrollbar.trough", "from", "default")
style.element_create("Custom.Vertical.Scrollbar.trough", "from", "default")

# Map thumb color based on state
style.map("Custom.Vertical.TScrollbar",
          background=[("pressed", "blue"), ("!pressed", "black")])

style.map("Custom.Horizontal.TScrollbar",
          background=[("pressed", "blue"), ("!pressed", "black")])

# Apply the custom style
vscroll = ttk.Scrollbar(root, orient="vertical", style="Custom.Vertical.TScrollbar")
hscroll = ttk.Scrollbar(root, orient="horizontal", style="Custom.Horizontal.TScrollbar")

text = tk.Text(root, wrap="none", yscrollcommand=vscroll.set, xscrollcommand=hscroll.set)
text.insert("end", "Scroll me!\n" * 50)

vscroll.config(command=text.yview)
hscroll.config(command=text.xview)

text.grid(row=0, column=0, sticky="nsew")
vscroll.grid(row=0, column=1, sticky="ns")
hscroll.grid(row=1, column=0, sticky="ew")

root.grid_rowconfigure(0, weight=1)
root.grid_columnconfigure(0, weight=1)

root.mainloop()
