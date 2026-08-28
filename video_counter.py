"""Genere une video MP4 (H.264) affichant un compteur hh:mm:ss[,ms]."""

import math
import queue
import subprocess
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

# Polices candidates par ordre de preference : Consolas est concue pour la
# lisibilite a l'ecran et, comme toute police a chasse fixe, garantit que
# chaque caractere occupe la meme largeur (le texte ne "bouge" pas d'image
# en image quand les chiffres changent).
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\consolab.ttf",
    r"C:\Windows\Fonts\courbd.ttf",
    r"C:\Windows\Fonts\CascadiaMono.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
]

MIN_HEIGHT_PX = 100
MAX_HEIGHT_PX = 500
DEFAULT_FPS = 30
FPS_CHOICES = [24, 25, 30, 50, 60]
TEXT_HEIGHT_RATIO = 0.8  # le texte occupe 80% de la hauteur demandee


def find_font_path() -> str | None:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return path
    return None


def build_filename(hours: int, minutes: int, seconds: int, with_ms: bool) -> str:
    suffix = ".ms" if with_ms else ""
    return f"{hours:02d}h{minutes:02d}m{seconds:02d}s{suffix}.mp4"


def format_timecode(elapsed_ms: int, with_ms: bool, show_hours: bool) -> str:
    hours, rem = divmod(elapsed_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, ms = divmod(rem, 1_000)
    if show_hours:
        base = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        base = f"{minutes:02d}:{seconds:02d}"
    return f"{base},{ms:03d}" if with_ms else base


@dataclass
class Layout:
    font: ImageFont.FreeTypeFont
    canvas_size: tuple[int, int]
    text_origin: tuple[int, int]


def _round_up_even(value: float) -> int:
    value = int(math.ceil(value))
    return value + 1 if value % 2 else value


def build_layout(font_path: str | None, height_px: int, with_ms: bool, show_hours: bool) -> Layout:
    sample = format_timecode(0, with_ms, show_hours)
    target_text_height = height_px * TEXT_HEIGHT_RATIO

    size = max(1, round(height_px))
    font = ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default(size)
    left, top, right, bottom = font.getbbox(sample)
    measured_height = bottom - top

    # Un seul ajustement suffit : la bbox reelle a la taille de depart donne
    # le ratio exact pour atteindre la hauteur cible.
    if measured_height > 0 and font_path:
        size = max(1, round(size * target_text_height / measured_height))
        font = ImageFont.truetype(font_path, size)
        left, top, right, bottom = font.getbbox(sample)

    text_width = right - left
    text_height = bottom - top
    margin = round((height_px - text_height) / 2)

    canvas_w = _round_up_even(text_width + 2 * margin)
    canvas_h = _round_up_even(height_px)
    origin_x = (canvas_w - text_width) // 2 - left
    origin_y = (canvas_h - text_height) // 2 - top

    return Layout(font, (canvas_w, canvas_h), (origin_x, origin_y))


def render_frame(layout: Layout, text: str) -> bytes:
    image = Image.new("RGB", layout.canvas_size, "black")
    draw = ImageDraw.Draw(image)
    draw.text(layout.text_origin, text, font=layout.font, fill="white")
    return image.tobytes()


def generate_video(
    duration_s: float,
    height_px: int,
    with_ms: bool,
    fps: int,
    output_path: str,
    progress_cb=None,
) -> None:
    show_hours = duration_s >= 3600
    font_path = find_font_path()
    layout = build_layout(font_path, height_px, with_ms, show_hours)
    width, height = layout.canvas_size
    total_frames = max(1, round(duration_s * fps))

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg_exe, "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}", "-r", str(fps),
        "-i", "-",
        "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
        "-movflags", "+faststart",
        output_path,
    ]
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    # Le texte ne change qu'une fois par ms (ou par seconde si with_ms est
    # desactive) : on reutilise l'image tant que le timecode ne change pas
    # plutot que de redessiner a chaque frame.
    last_text = None
    last_frame_bytes = b""
    try:
        for frame_index in range(total_frames):
            elapsed_ms = round(frame_index * 1000 / fps)
            text = format_timecode(elapsed_ms, with_ms, show_hours)
            if text != last_text:
                last_frame_bytes = render_frame(layout, text)
                last_text = text
            process.stdin.write(last_frame_bytes)
            if progress_cb is not None and frame_index % max(1, fps) == 0:
                progress_cb(frame_index + 1, total_frames)
        if progress_cb is not None:
            progress_cb(total_frames, total_frames)
    finally:
        process.stdin.close()
        stderr_output = process.stderr.read()
        process.wait()

    if process.returncode != 0:
        raise RuntimeError(f"ffmpeg a echoue (code {process.returncode}) :\n{stderr_output.decode(errors='ignore')}")


class CounterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Timecode Counter Generator")
        self.resizable(False, False)
        self._progress_queue = queue.Queue()
        self._build_widgets()

    def _build_widgets(self):
        pad = {"padx": 8, "pady": 4}
        frm = ttk.Frame(self, padding=12)
        frm.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frm, text="Duration (end of counter)").grid(row=0, column=0, columnspan=2, sticky="w", **pad)
        dur_frame = ttk.Frame(frm)
        dur_frame.grid(row=1, column=0, columnspan=2, sticky="w", **pad)
        self.hours_var = tk.IntVar(value=0)
        self.minutes_var = tk.IntVar(value=1)
        self.seconds_var = tk.IntVar(value=0)
        self.hours_var.trace_add("write", self._update_filename)
        self.minutes_var.trace_add("write", self._update_filename)
        self.seconds_var.trace_add("write", self._update_filename)
        ttk.Spinbox(dur_frame, from_=0, to=99, width=4, textvariable=self.hours_var).grid(row=0, column=0)
        ttk.Label(dur_frame, text="h").grid(row=0, column=1, padx=(2, 8))
        ttk.Spinbox(dur_frame, from_=0, to=59, width=4, textvariable=self.minutes_var).grid(row=0, column=2)
        ttk.Label(dur_frame, text="m").grid(row=0, column=3, padx=(2, 8))
        ttk.Spinbox(dur_frame, from_=0, to=59, width=4, textvariable=self.seconds_var).grid(row=0, column=4)
        ttk.Label(dur_frame, text="s").grid(row=0, column=5, padx=(2, 0))

        self.with_ms_var = tk.BooleanVar(value=True)
        self.with_ms_var.trace_add("write", self._update_filename)
        ttk.Checkbutton(frm, text="Show milliseconds", variable=self.with_ms_var).grid(
            row=2, column=0, columnspan=2, sticky="w", **pad
        )

        ttk.Label(frm, text=f"Text height in px ({MIN_HEIGHT_PX}-{MAX_HEIGHT_PX})").grid(
            row=3, column=0, sticky="w", **pad
        )
        self.height_var = tk.IntVar(value=200)
        ttk.Spinbox(
            frm, from_=MIN_HEIGHT_PX, to=MAX_HEIGHT_PX, textvariable=self.height_var, width=6
        ).grid(row=3, column=1, sticky="w", **pad)

        ttk.Label(frm, text="Frame rate (fps)").grid(row=4, column=0, sticky="w", **pad)
        self.fps_var = tk.StringVar(value=str(DEFAULT_FPS))
        ttk.Combobox(
            frm, values=[str(v) for v in FPS_CHOICES], textvariable=self.fps_var, width=6, state="readonly"
        ).grid(row=4, column=1, sticky="w", **pad)

        ttk.Label(frm, text="Output folder").grid(row=5, column=0, sticky="w", **pad)
        out_frame = ttk.Frame(frm)
        out_frame.grid(row=6, column=0, columnspan=2, sticky="we", **pad)
        self.output_dir_var = tk.StringVar(value=str(Path(__file__).resolve().parent))
        ttk.Entry(out_frame, textvariable=self.output_dir_var, width=32).grid(row=0, column=0)
        ttk.Button(out_frame, text="Browse...", command=self._browse_output_dir).grid(row=0, column=1, padx=(6, 0))

        # Le nom de fichier est toujours derive de la duree (jamais editable
        # a la main) : deux compteurs de meme duree portent donc toujours le
        # meme nom, ce qui evite de regenerer une version deja existante.
        self.filename_var = tk.StringVar(value="")
        ttk.Label(frm, textvariable=self.filename_var).grid(row=7, column=0, columnspan=2, sticky="w", **pad)
        self._update_filename()

        self.progress_var = tk.DoubleVar(value=0)
        ttk.Progressbar(frm, maximum=100, variable=self.progress_var).grid(
            row=8, column=0, columnspan=2, sticky="we", **pad
        )
        self.status_var = tk.StringVar(value="")
        ttk.Label(frm, textvariable=self.status_var).grid(row=9, column=0, columnspan=2, sticky="w", **pad)

        self.generate_btn = ttk.Button(frm, text="Generate video", command=self._on_generate)
        self.generate_btn.grid(row=10, column=0, columnspan=2, pady=(10, 0))

    def _update_filename(self, *_args):
        try:
            name = build_filename(
                self.hours_var.get(), self.minutes_var.get(), self.seconds_var.get(), self.with_ms_var.get()
            )
        except tk.TclError:
            return
        self.filename_var.set(f"File name: {name}")

    def _browse_output_dir(self):
        path = filedialog.askdirectory(initialdir=self.output_dir_var.get() or str(Path(__file__).resolve().parent))
        if path:
            self.output_dir_var.set(path)

    def _on_generate(self):
        try:
            duration_s = self.hours_var.get() * 3600 + self.minutes_var.get() * 60 + self.seconds_var.get()
            height_px = self.height_var.get()
            fps = int(self.fps_var.get())
        except tk.TclError:
            messagebox.showerror("Erreur", "Merci de saisir des valeurs numeriques valides.")
            return

        if duration_s <= 0:
            messagebox.showerror("Erreur", "La duree doit etre superieure a 0.")
            return
        if not (MIN_HEIGHT_PX <= height_px <= MAX_HEIGHT_PX):
            messagebox.showerror("Erreur", f"La hauteur doit etre comprise entre {MIN_HEIGHT_PX} et {MAX_HEIGHT_PX} px.")
            return
        output_dir = self.output_dir_var.get().strip()
        if not output_dir:
            messagebox.showerror("Erreur", "Choisissez un dossier de sortie.")
            return

        filename = build_filename(
            self.hours_var.get(), self.minutes_var.get(), self.seconds_var.get(), self.with_ms_var.get()
        )
        output_path = Path(output_dir) / filename
        if output_path.exists():
            if not messagebox.askyesno(
                "Fichier existant",
                f"Une video de cette duree existe deja :\n{output_path}\n\nL'ecraser ?",
            ):
                return
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path = str(output_path)

        self.generate_btn.config(state="disabled")
        self.status_var.set("Generation en cours...")
        self.progress_var.set(0)

        worker = threading.Thread(
            target=self._run_generation,
            args=(duration_s, height_px, self.with_ms_var.get(), fps, output_path),
            daemon=True,
        )
        worker.start()
        self.after(100, self._poll_progress)

    def _run_generation(self, duration_s, height_px, with_ms, fps, output_path):
        try:
            def on_progress(done, total):
                self._progress_queue.put(("progress", done, total))

            generate_video(duration_s, height_px, with_ms, fps, output_path, progress_cb=on_progress)
            self._progress_queue.put(("done", output_path))
        except Exception as exc:
            self._progress_queue.put(("error", str(exc)))

    def _poll_progress(self):
        try:
            while True:
                kind, *payload = self._progress_queue.get_nowait()
                if kind == "progress":
                    done, total = payload
                    self.progress_var.set(done / total * 100)
                    self.status_var.set(f"Generation en cours... {done}/{total} images")
                elif kind == "done":
                    self.progress_var.set(100)
                    self.status_var.set("Termine.")
                    self.generate_btn.config(state="normal")
                    messagebox.showinfo("Termine", f"Video generee :\n{payload[0]}")
                    return
                elif kind == "error":
                    self.status_var.set("Erreur.")
                    self.generate_btn.config(state="normal")
                    messagebox.showerror("Erreur", payload[0])
                    return
        except queue.Empty:
            pass
        self.after(100, self._poll_progress)


if __name__ == "__main__":
    CounterApp().mainloop()
