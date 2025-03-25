import time
from typing import Any
import taichi as ti


class Taichi:
    """Taichi class for initializing Taichi and UI.
    
    This class provides a show method for displaying the Taichi canvas.
    It is used by the TolveraContext class to manage a window.
    """

    def __init__(self, context, **kwargs) -> None:
        """Initialize Taichi.
        
        Args:
            context (TolveraContext): Global TolveraContext instance.
            **kwargs: Keyword arguments:
                gpu (str): GPU architecture to use. Defaults to "vulkan".
                cpu (bool): Use CPU instead of GPU. Defaults to False.
                fps (int): FPS limit. Defaults to 120.
                seed (int): Random seed. Defaults to current time.
                headless (bool): Run headless mode. Defaults to False.
                name (str): Window name. Defaults to "Tölvera".
        """
        self.ctx = context
        # Removed unnecessary storage of `kwargs`, directly extracting only required values
        self.gpu = kwargs.get("gpu", "vulkan")
        self.cpu = kwargs.get("cpu", False)
        self.fps = kwargs.get("fps", 120)
        self.seed = kwargs.get("seed", int(time.time()))
        self.headless = kwargs.get("headless", False)
        self.name = kwargs.get("name", "Tölvera")

        self.init_ti()
        self.init_ui()
        print(f"[Tölvera.Taichi] Taichi initialized with: {vars(self)}")

    def init_ti(self):
        """Initialize Taichi backend with the selected architecture."""
        if self.cpu:
            ti.init(arch=ti.cpu, random_seed=self.seed)
            self.gpu = None  # Ensure GPU is set to None when using CPU
            print("[Tölvera.Taichi] Running on CPU")
        else:
            # Used a dictionary lookup instead of multiple if-elif conditions
            arch_map = {"vulkan": ti.vulkan, "metal": ti.metal, "cuda": ti.cuda}
            if self.gpu in arch_map:
                ti.init(arch=arch_map[self.gpu], random_seed=self.seed)
                print(f"[Tölvera.Taichi] Running on {self.gpu}")
            else:
                print(f"[Tölvera.Taichi] Invalid GPU: {self.gpu}")  # Improved error handling

    def init_ui(self):
        """Initialize Taichi UI window and canvas."""
        self.window = ti.ui.Window(
            self.name, (self.ctx.x, self.ctx.y),
            fps_limit=self.fps, show_window=not self.headless
        )
        self.canvas = self.window.get_canvas()
        self.gui = self.window.get_gui()

    def show(self, px):
        """Display the Taichi canvas and show the window."""
        self.canvas.set_image(px.px.rgba)
        if not self.headless:
            self.window.show()

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Call Taichi window show."""
        self.show(*args, **kwargs)  # Improved readability and kept structure intact
