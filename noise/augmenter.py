import numpy as np
import tkinter as tk
from PIL import Image, ImageDraw
import argparse

# Logical mask size (output)
WIDTH, HEIGHT = 128, 128
# GUI scale (drawing view is 4x larger)
SCALE = 4
CANVAS_WIDTH, CANVAS_HEIGHT = WIDTH * SCALE, HEIGHT * SCALE
BRUSH_SIZE = 3  # in mask pixels (logical)

parser = argparse.ArgumentParser(
    description="Creates a 128x128 mask by drawing on a GUI."
)
parser.add_argument(
    "--file-name",
    "-f",
    default="mask.txt",
    help="Filename of the output file (default: mask.txt)",
)
parser.add_argument(
    "--output-dir",
    "-o",
    default="outputs",
    help="Directory to save output mask (default: outputs)",
)
args = parser.parse_args()
output_head = args.output_dir
output_tail = args.file_name


class MaskDrawer:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Draw Binary Mask ({WIDTH}x{HEIGHT}) — {SCALE}x zoom")

        # PIL image to store the actual mask drawing at 128x128
        self.image = Image.new("L", (WIDTH, HEIGHT), 0)  # black = 0
        self.draw = ImageDraw.Draw(self.image)

        # Tkinter Canvas for user to draw at 512x512 (4x)
        self.canvas = tk.Canvas(
            root, width=CANVAS_WIDTH, height=CANVAS_HEIGHT, bg="white", cursor="cross"
        )
        self.canvas.pack()

        # Buttons
        self.button_frame = tk.Frame(root)
        self.button_frame.pack(fill="x")
        tk.Button(self.button_frame, text="Clear", command=self.clear_canvas).pack(
            side="left", expand=True, fill="x"
        )
        tk.Button(self.button_frame, text="Done", command=self.finish).pack(
            side="right", expand=True, fill="x"
        )

        # Mouse bindings
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        self.last_x, self.last_y = None, None
        self.done = False

    def gui_to_img(self, x_gui, y_gui):
        """Map GUI (scaled) coords to image (logical mask) coords."""
        x = max(0, min(WIDTH - 1, int(x_gui // SCALE)))
        y = max(0, min(HEIGHT - 1, int(y_gui // SCALE)))
        return x, y

    def draw_segment(self, x0g, y0g, x1g, y1g):
        """Draw line segment on both GUI (scaled) and PIL image (logical)."""
        # GUI line (scaled)
        self.canvas.create_line(
            x0g,
            y0g,
            x1g,
            y1g,
            fill="black",
            width=BRUSH_SIZE * SCALE,
            capstyle=tk.ROUND,
            smooth=True,
        )
        # Image line (logical)
        x0, y0 = self.gui_to_img(x0g, y0g)
        x1, y1 = self.gui_to_img(x1g, y1g)
        self.draw.line((x0, y0, x1, y1), fill=255, width=BRUSH_SIZE, joint=None)

    def on_press(self, event):
        self.last_x, self.last_y = event.x, event.y
        # Draw a dot in case of single click
        r_gui = (BRUSH_SIZE * SCALE) / 2
        self.canvas.create_oval(
            event.x - r_gui,
            event.y - r_gui,
            event.x + r_gui,
            event.y + r_gui,
            fill="black",
            outline="black",
        )
        x, y = self.gui_to_img(event.x, event.y)
        r = BRUSH_SIZE / 2
        self.draw.ellipse((x - r, y - r, x + r, y + r), fill=255)

    def on_drag(self, event):
        if self.last_x is not None and self.last_y is not None:
            self.draw_segment(self.last_x, self.last_y, event.x, event.y)
        self.last_x, self.last_y = event.x, event.y

    def on_release(self, _event):
        self.last_x, self.last_y = None, None

    def clear_canvas(self):
        self.canvas.delete("all")
        self.image = Image.new("L", (WIDTH, HEIGHT), 0)
        self.draw = ImageDraw.Draw(self.image)

    def finish(self):
        self.done = True
        self.root.destroy()


def get_mask_from_gui():
    root = tk.Tk()
    app = MaskDrawer(root)
    root.mainloop()

    # Convert PIL image (128x128) to a binary NumPy mask (0/1)
    mask = np.array(app.image)
    mask = (mask > 127).astype(np.uint8)
    return mask


# Example usage:
if __name__ == "__main__":
    mask = get_mask_from_gui()
    print("Mask shape:", mask.shape)  # (128, 128)
    print("Mask dtype:", mask.dtype)  # uint8

    #  Flatten
    mask = mask.reshape(1, WIDTH * HEIGHT)
    np.savetxt(f"{output_head}/{output_tail}", mask, fmt="%d", delimiter=" ")
    print(f"Mask has been saved to {output_head}/{output_tail}")
