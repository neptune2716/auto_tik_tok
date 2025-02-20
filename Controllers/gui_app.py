import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import queue
import time
import logging
from datetime import datetime
import humanize
import json

# Import project functions and settings manager
from main import find_next_project_id
from reddit_story import get_story
from story_video_generator import process_story_video
from story_history import StoryHistory
from config import BASE_VIDEO, OUTPUT_DIR, VOICE_OPTIONS
from settings_manager import load_settings, save_settings

# Custom styles for dark theme
THEMES = {
    "black": {
        "bg": "#1e1e1e",           # Dark background
        "fg": "#d4d4d4",           # Light gray text
        "button_bg": "#2d2d2d",    # Slightly lighter background for buttons
        "button_fg": "#cccccc",    # Light gray for button text
        "progress_bg": "#2d2d2d",  # Progress bar background
        "progress_fg": "#4CAF50",  # Material green for progress
        "error_fg": "#f44336",     # Material red for errors
        "success_fg": "#4CAF50",   # Material green for success
        "info_fg": "#2196F3",      # Material blue for info
        "table_bg": "#252526",     # Slightly different dark for table
        "table_fg": "#d4d4d4",     # Light gray for table text
        "table_selected": "#37373d" # Highlighted row background
    },
    "white": {
        "bg": "#ffffff",
        "fg": "#000000",
        "button_bg": "#e0e0e0",
        "button_fg": "#000000",
        "progress_bg": "#e0e0e0",
        "progress_fg": "#00aa00",
        "error_fg": "#ff0000",
        "success_fg": "#008800",
        "info_fg": "#0000ff",
        "table_bg": "#ffffff",
        "table_fg": "#000000",
        "table_selected": "#e0e0e0"
    }
}

# Thread-safe queue for log messages
log_queue = queue.Queue()

# Add path for videos database
VIDEOS_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "videos.json")

class GuiApp:
    def __init__(self, master):
        self.master = master
        master.title("Reddit Story Video Generator")
        self.settings = load_settings()

        # Initialize databases and state variables first
        self.load_videos_db()  # Move this up
        self.current_theme = self.settings.get("theme", "black")
        self.STYLES = THEMES[self.current_theme]
        self.current_segment = 0
        self.total_segments = 0
        self.start_time = None
        self.writing_progress = 0  # Add progress tracking
        self.last_video = None

        # Then configure UI
        self.configure_theme()
        self.create_widgets()
        self.poll_log_queue()
        self.setup_logging()


    def configure_theme(self):
        style = ttk.Style()
        style.theme_use('default')  # Reset to default theme first
        
        # Configure common elements
        style.configure(".", 
            background=self.STYLES["bg"],
            foreground=self.STYLES["fg"],
            fieldbackground=self.STYLES["bg"],
            selectbackground=self.STYLES["table_selected"],
            selectforeground=self.STYLES["fg"]
        )
        
        # Configure specific elements
        style.configure("Treeview", 
            background=self.STYLES["table_bg"],
            foreground=self.STYLES["table_fg"],
            fieldbackground=self.STYLES["table_bg"]
        )
        style.configure("Treeview.Heading",
            background=self.STYLES["button_bg"],
            foreground=self.STYLES["button_fg"]
        )
        style.map("Treeview",
            background=[('selected', self.STYLES["table_selected"])],
            foreground=[('selected', self.STYLES["fg"])]
        )
        
        # Configure Notebook (tabs)
        style.configure("TNotebook", 
            background=self.STYLES["bg"],
            tabmargins=[2, 5, 2, 0]
        )
        style.configure("TNotebook.Tab",
            background=self.STYLES["button_bg"],
            foreground=self.STYLES["button_fg"],
            padding=[10, 2]
        )
        style.map("TNotebook.Tab",
            background=[("selected", self.STYLES["bg"])],
            foreground=[("selected", self.STYLES["fg"])]
        )
        
        # Configure other elements
        style.configure("TButton", 
            background=self.STYLES["button_bg"],
            foreground=self.STYLES["button_fg"]
        )
        style.map("TButton",
            background=[('active', self.STYLES["table_selected"])],
            foreground=[('active', self.STYLES["fg"])]
        )
        
        style.configure("TFrame", background=self.STYLES["bg"])
        style.configure("TLabel", background=self.STYLES["bg"], foreground=self.STYLES["fg"])
        
        # Configure Combobox
        style.configure("TCombobox",
            fieldbackground=self.STYLES["table_bg"],
            background=self.STYLES["button_bg"],
            foreground=self.STYLES["fg"],
            selectbackground=self.STYLES["table_selected"],
            selectforeground=self.STYLES["fg"]
        )
        style.map("TCombobox",
            fieldbackground=[('readonly', self.STYLES["table_bg"])],
            selectbackground=[('readonly', self.STYLES["table_selected"])]
        )
        
        # Configure Scrollbar
        style.configure("TScrollbar",
            background=self.STYLES["button_bg"],
            troughcolor=self.STYLES["bg"],
            arrowcolor=self.STYLES["fg"]
        )
        
        # Set TEntry text color to classic black
        style.configure("TEntry", foreground="black")

    def create_widgets(self):
        notebook = ttk.Notebook(self.master)
        notebook.pack(expand=True, fill='both', padx=10, pady=10)

        # Generate Video Tab
        self.gen_frame = ttk.Frame(notebook)
        notebook.add(self.gen_frame, text="Generate Video")

        # Status frame
        status_frame = ttk.Frame(self.gen_frame)
        status_frame.pack(fill='x', padx=10, pady=5)

        self.gen_button = ttk.Button(status_frame, text="Generate New Video", command=self.start_generation)
        self.gen_button.pack(side='left', padx=5)

        self.preview_button = ttk.Button(status_frame, text="Preview Last Video",
                                       command=self.preview_video, state='disabled')
        self.preview_button.pack(side='left', padx=5)

        # Progress frame
        progress_frame = ttk.Frame(self.gen_frame)
        progress_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(progress_frame, text="Overall Progress:").pack(fill='x')
        self.overall_progress = ttk.Progressbar(progress_frame, length=300, mode='determinate')
        self.overall_progress.pack(fill='x', pady=2)

        ttk.Label(progress_frame, text="Part Progress:").pack(fill='x')  # Changed from "Segment Progress"
        self.part_progress = ttk.Progressbar(progress_frame, length=300, mode='determinate')  # Renamed from segment_progress
        self.part_progress.pack(fill='x', pady=2)

        # Status labels
        info_frame = ttk.Frame(self.gen_frame)
        info_frame.pack(fill='x', padx=10, pady=5)

        self.status_label = ttk.Label(info_frame, text="Status: Idle")
        self.status_label.pack(fill='x')

        self.part_label = ttk.Label(info_frame, text="Part: -")  # Changed from "Segment: -"
        self.part_label.pack(fill='x')

        self.time_label = ttk.Label(info_frame, text="Estimated time remaining: -")
        self.time_label.pack(fill='x')

        self.size_label = ttk.Label(info_frame, text="Generated file size: -")
        self.size_label.pack(fill='x')

        # Add Videos Table to Generation Tab
        videos_frame = ttk.Frame(self.gen_frame)
        videos_frame.pack(fill='both', expand=True, padx=10, pady=5)

        # Exclude "id" from extra columns; the tree column (#0) will show id
        extra_columns = ('title', 'date', 'status', 'length', 'parts')
        # Use native tree column by setting show to "tree headings"
        self.videos_tree = ttk.Treeview(videos_frame, columns=extra_columns, show='tree headings', height=6)
        # Configure tree column (#0) as ID
        self.videos_tree.heading("#0", text="ID")
        self.videos_tree.column("#0", width=50, anchor='center')
        for col in extra_columns:
            self.videos_tree.heading(col, text=col.title())
            self.videos_tree.column(col, width=100, anchor='center')

        # Right-click menu for copying text
        self.tree_menu = tk.Menu(self.master, tearoff=0)
        self.tree_menu.add_command(label="Copier le texte", command=self.copy_cell_text)
        self.tree_menu.add_command(label="Ouvrir", command=self.open_selected_video)
        self.tree_menu.add_command(label="Supprimer", command=self.delete_selected_video)
        
        # Bind right-click to show menu
        self.videos_tree.bind('<Button-3>', self.show_tree_menu)
        # Bind key events: Delete for deletion, Return (Enter) for opening
        self.videos_tree.bind('<Delete>', lambda event: self.delete_selected_video(event))
        self.videos_tree.bind('<Return>', lambda event: self.open_selected_video(event))
        
        # Add scrollbars
        y_scrollbar = ttk.Scrollbar(videos_frame, orient="vertical", command=self.videos_tree.yview)
        x_scrollbar = ttk.Scrollbar(videos_frame, orient="horizontal", command=self.videos_tree.xview)
        self.videos_tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)

        # Pack widgets
        self.videos_tree.grid(row=0, column=0, sticky='nsew')
        y_scrollbar.grid(row=0, column=1, sticky='ns')
        x_scrollbar.grid(row=1, column=0, sticky='ew')

        # Configure grid weights
        videos_frame.grid_columnconfigure(0, weight=1)
        videos_frame.grid_rowconfigure(0, weight=1)

        # History Tab
        self.history_frame = ttk.Frame(notebook)
        notebook.add(self.history_frame, text="History")
        self.history_list = tk.Listbox(self.history_frame, height=10)
        self.history_list.pack(side='left', fill='both', expand=True, padx=10, pady=10)
        scrollbar = ttk.Scrollbar(self.history_frame, orient="vertical", command=self.history_list.yview)
        scrollbar.pack(side='right', fill='y')
        self.history_list.config(yscrollcommand=scrollbar.set)
        self.clear_history_button = ttk.Button(self.history_frame, text="Clear History", command=self.clear_history)
        self.clear_history_button.pack(padx=10, pady=5)
        self.refresh_history()

        # Settings Tab
        self.settings_frame = ttk.Frame(notebook)
        notebook.add(self.settings_frame, text="Settings")

        # Voice settings with random option
        ttk.Label(self.settings_frame, text="TTS Voice:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
        self.voice_var = tk.StringVar(value=self.settings.get("voice"))
        voice_options = ["random"] + VOICE_OPTIONS
        self.voice_dropdown = ttk.Combobox(self.settings_frame, textvariable=self.voice_var,
                                         values=voice_options, state="readonly")
        self.voice_dropdown.grid(row=0, column=1, columnspan=2, padx=10, pady=5, sticky='ew')

        # Subreddit management
        ttk.Label(self.settings_frame, text="Current Subreddit:").grid(row=1, column=0, padx=10, pady=5, sticky='w')
        self.subreddit_var = tk.StringVar(value=self.settings.get("subreddit"))
        self.subreddit_dropdown = ttk.Combobox(self.settings_frame, textvariable=self.subreddit_var,
                                             values=self.settings.get("subreddits", []), state="readonly")
        self.subreddit_dropdown.grid(row=1, column=1, columnspan=2, padx=10, pady=5, sticky='ew')

        # Add new subreddit
        ttk.Label(self.settings_frame, text="Add Subreddit:").grid(row=2, column=0, padx=10, pady=5, sticky='w')
        self.new_subreddit_var = tk.StringVar()
        ttk.Entry(self.settings_frame, textvariable=self.new_subreddit_var).grid(row=2, column=1, padx=10, pady=5, sticky='ew')
        ttk.Button(self.settings_frame, text="Add", command=self.add_subreddit).grid(row=2, column=2, padx=5, pady=5)

        # Segment length settings
        ttk.Label(self.settings_frame, text="Min words per segment:").grid(row=3, column=0, padx=10, pady=5, sticky='w')
        self.min_words_var = tk.StringVar(value=str(self.settings.get("min_words_segment", 150)))
        ttk.Entry(self.settings_frame, textvariable=self.min_words_var).grid(row=3, column=1, padx=10, pady=5, sticky='ew')

        ttk.Label(self.settings_frame, text="Max words per segment:").grid(row=4, column=0, padx=10, pady=5, sticky='w')
        self.max_words_var = tk.StringVar(value=str(self.settings.get("max_words_segment", 225)))
        ttk.Entry(self.settings_frame, textvariable=self.max_words_var).grid(row=4, column=1, padx=10, pady=5, sticky='ew')

        self.save_settings_button = ttk.Button(self.settings_frame, text="Save Settings", command=self.save_settings)
        self.save_settings_button.grid(row=5, column=0, columnspan=3, pady=20)

        # Theme settings
        ttk.Label(self.settings_frame, text="Theme:").grid(row=6, column=0, padx=10, pady=5, sticky='w')
        self.theme_var = tk.StringVar(value=self.current_theme)
        self.theme_dropdown = ttk.Combobox(self.settings_frame, textvariable=self.theme_var,
                                         values=list(THEMES.keys()), state="readonly")
        self.theme_dropdown.grid(row=6, column=1, columnspan=2, padx=10, pady=5, sticky='ew')

        # Enhanced Logs Tab
        self.log_frame = ttk.Frame(notebook)
        notebook.add(self.log_frame, text="Logs")

        # Log Text Area
        self.log_text = tk.Text(self.log_frame, state='disabled', bg=self.STYLES["bg"], fg=self.STYLES["fg"], wrap=tk.WORD)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Scrollbar for the Log Text Area
        self.log_scrollbar = ttk.Scrollbar(self.log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text['yscrollcommand'] = self.log_scrollbar.set

        # Configure tags for colored logging
        self.log_text.tag_config("info", foreground=self.STYLES["info_fg"])
        self.log_text.tag_config("success", foreground=self.STYLES["success_fg"])
        self.log_text.tag_config("error", foreground=self.STYLES["error_fg"])

        # Clear Logs Button
        self.clear_logs_button = ttk.Button(self.log_frame, text="Clear Logs",command=self.clear_logs)
        self.clear_logs_button.pack(pady=5)

        # Fix history list background
        self.history_list.configure(bg=self.STYLES["bg"], fg=self.STYLES["fg"])

        # Load existing videos
        self.refresh_videos_list()

    def show_tree_menu(self, event):
        """Show context menu at mouse position"""
        try:
            item = self.videos_tree.identify_row(event.y)
            column = self.videos_tree.identify_column(event.x)
            
            if item and column:
                # Select the cell
                self.videos_tree.selection_set(item)
                # Save the column number for later use
                self.selected_column = int(column[1]) - 1  # Convert #1,#2,etc to 0,1,etc
                # Show the menu
                self.tree_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.tree_menu.grab_release()

    def copy_cell_text(self):
        """Copy the text from the selected cell"""
        selection = self.videos_tree.selection()
        if selection and hasattr(self, 'selected_column'):
            item = selection[0]
            text = str(self.videos_tree.item(item)['values'][self.selected_column])
            self.master.clipboard_clear()
            self.master.clipboard_append(text)
            self.log_info("Copied cell text to clipboard")

    def start_generation(self):
        self.gen_button.config(state='disabled')
        self.preview_button.config(state='disabled')
        self.overall_progress['value'] = 0
        self.part_progress['value'] = 0
        self.start_time = time.time()
        self.current_segment = 0

        # Get the selected voice before starting the thread
        selected_voice = self.voice_var.get()
        thread = threading.Thread(target=self.generate_video_thread, args=(selected_voice,), daemon=True)
        thread.start()

    def generate_video_thread(self, selected_voice):
        try:
            # Generate Project ID
            project_id = find_next_project_id()
            self.log_info(f"Starting new project: {project_id}")

            # Update progress (10%)
            self.master.after(0, lambda: self.overall_progress.config(value=10))
            self.set_status("Fetching story...", "info")

            # Fetch story
            subreddit = self.subreddit_var.get()
            title, story, history = get_story(subreddit, project_id)
            self.log_info(f"Fetched story: {title}")

            # Update progress (30%)
            self.master.after(0, lambda: self.overall_progress.config(value=30))
            self.set_status("Generating video...", "info")

            # Calculate parts (changed from segments)
            parts = len(story.split('\n\n'))
            self.total_segments = parts  # Keep variable name for compatibility
            self.update_segment_info(0, parts)  # Changed to use parts

            # Process video with selected voice and progress callback
            output_files = process_story_video(
                BASE_VIDEO,
                title,
                story,
                project_id,
                voice=selected_voice,
                progress_callback=self.update_progress
            )

            # Success handling
            history.add_story(title)
            self.log_success("Video generation successful!")
            self.set_status("Complete!", "success")
            self.master.after(0, lambda: self.overall_progress.config(value=100))

            # Update UI with file info
            if output_files:
                self.last_video = output_files[0]
                size = os.path.getsize(self.last_video)
                self.size_label.config(text=f"Generated file size: {humanize.naturalsize(size)}")
                self.preview_button.config(state='normal')

            # After successful generation, add to videos database
            self.add_video_to_db(project_id, title, output_files)
            self.master.after(0, self.refresh_videos_list)

        except Exception as e:
            self.log_error(f"Error: {str(e)}")
            self.set_status("Error during generation", "error")
            messagebox.showerror("Error", str(e))
            # If error occurs during generation
            if 'project_id' in locals():
                self.videos_db[project_id] = {
                    'title': title if 'title' in locals() else 'Unknown',
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'status': f'Error: {str(e)}',
                    'length': '-',
                    'parts': 0,
                    'files': []
                }
                self.save_videos_db()
                self.master.after(0, self.refresh_videos_list)
        finally:
            self.gen_button.config(state='normal')

    def update_segment_info(self, current, total):
        """Update the progress info in the GUI"""
        self.current_segment = current
        self.master.after(0, lambda: self.part_label.config(text=f"Part: {current}/{total}"))  # Changed from segment_label
        progress = (current / total) * 100 if total > 0 else 0
        self.master.after(0, lambda: self.part_progress.config(value=progress))  # Changed from segment_progress

        if self.start_time and current > 0:
            elapsed = time.time() - self.start_time
            remaining = (elapsed / current) * (total - current)
            self.master.after(0, lambda: self.time_label.config(text=f"Estimated time remaining: {humanize.naturaltime(remaining)}"))

    def set_status(self, message, status_type="info"):
        color = self.STYLES.get(f"{status_type}_fg", self.STYLES["fg"])
        self.master.after(0, lambda: self.status_label.config(text=f"Status: {message}", foreground=color))

    def log_info(self, message):
        self.append_log(message, "info")

    def log_success(self, message):
        self.append_log(message, "success")

    def log_error(self, message):
        self.append_log(message, "error")

    def append_log(self, message, tag):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, f"[{timestamp}] ", "timestamp")
        self.log_text.insert(tk.END, message + "\n", tag)
        self.log_text.tag_config("timestamp", foreground="#808080")  # Gray timestamp
        self.log_text.tag_config("info", foreground=self.STYLES["info_fg"])
        self.log_text.tag_config("success", foreground=self.STYLES["success_fg"])
        self.log_text.tag_config("error", foreground=self.STYLES["error_fg"])
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')

    def clear_logs(self):
        self.log_text.config(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state='disabled')

    def refresh_history(self):
        # Load used stories from history file.
        history = StoryHistory()
        self.history_list.delete(0, tk.END)
        for title in sorted(history.used_titles):
            self.history_list.insert(tk.END, title)

    def clear_history(self):
        if messagebox.askyesno("Confirm", "Clear all history?"):
            history = StoryHistory()
            history.clear_history()
            self.refresh_history()
            log_queue.put("History cleared.")

    def save_settings(self):
        try:
            # Validate segment lengths
            min_words = int(self.min_words_var.get())
            max_words = int(self.max_words_var.get())

            if min_words < 50:
                raise ValueError("Minimum words per segment must be at least 50")
            if max_words > 500:
                raise ValueError("Maximum words per segment must be less than 500")
            if min_words >= max_words:
                raise ValueError("Maximum words must be greater than minimum words")

            # Save all settings
            self.settings.update({
                "voice": self.voice_var.get(),
                "subreddit": self.subreddit_var.get(),
                "theme": self.theme_var.get(),
                "min_words_segment": min_words,
                "max_words_segment": max_words
            })

            save_settings(self.settings)

            # Apply theme if changed
            if self.theme_var.get() != self.current_theme:
                self.current_theme = self.theme_var.get()
                self.STYLES = THEMES[self.current_theme]
                self.configure_theme()

            self.log_info("Settings saved successfully")
            messagebox.showinfo("Settings", "Settings have been saved.\nSome changes may require restart to take effect.")
        except ValueError as e:
            messagebox.showerror("Invalid Settings", str(e))
            return

    def preview_video(self):
        if hasattr(self, "last_video") and os.path.exists(self.last_video):
            try:
                os.startfile(self.last_video)
            except Exception as e:
                messagebox.showerror("Preview Error", str(e))

    def poll_log_queue(self):
        try:
            while True:
                msg = log_queue.get_nowait()
                self.append_log(msg, "info")  # Treat all queue messages as info
        except queue.Empty:
            pass  # No more messages in the queue
        self.master.after(100, self.poll_log_queue)

    def load_videos_db(self):
        """Load videos database from JSON file"""
        if os.path.exists(VIDEOS_DB):
            try:
                with open(VIDEOS_DB, 'r', encoding='utf-8') as f:
                    self.videos_db = json.load(f)
            except Exception as e:
                self.log_error(f"Error loading videos database: {e}")
                self.videos_db = {}
        else:
            self.videos_db = {}

    def save_videos_db(self):
        """Save videos database to JSON file"""
        os.makedirs(os.path.dirname(VIDEOS_DB), exist_ok=True)
        with open(VIDEOS_DB, 'w', encoding='utf-8') as f:
            json.dump(self.videos_db, f, indent=2)

    def refresh_videos_list(self):
        # Clear current items
        for item in self.videos_tree.get_children():
            self.videos_tree.delete(item)

        # Add videos from database as parent rows, with child rows for parts if applicable.
        for video_id, data in sorted(self.videos_db.items(), reverse=True):
            # Insert parent row: use video_id as tree column text
            parent_values = (
                data.get('title', 'Unknown'),
                data.get('date', ''),
                data.get('status', 'Unknown'),
                data.get('length', ''),
                data.get('parts', '1')
            )
            parent_iid = str(video_id)
            self.videos_tree.insert('', 'end', iid=parent_iid, text=str(video_id), values=parent_values)
            files = data.get('files', [])
            if len(files) > 1:  # More than one part exists
                for idx, file in enumerate(files, start=1):
                    # Compute individual part length if file exists; else "Generating"
                    if os.path.exists(file):
                        try:
                            from moviepy.editor import VideoFileClip
                            with VideoFileClip(file) as clip:
                                part_length = humanize.precisedelta(clip.duration)
                        except Exception:
                            part_length = 'N/A'
                    else:
                        part_length = 'Generating'
                    child_values = (
                        f"{data.get('title', 'Unknown')} (Part {idx})",
                        data.get('date', ''),
                        data.get('status', 'Unknown'),
                        part_length,
                        ''  # Leave parts column empty
                    )
                    child_iid = f"{parent_iid}_part_{idx}"
                    self.videos_tree.insert(parent_iid, 'end', iid=child_iid, text="", values=child_values)

    def open_selected_video(self, event=None):
        selections = self.videos_tree.selection()
        for item in selections:
            if "_part_" in item:
                # Child row handling
                parent_id, part_str = item.split("_part_")
                try:
                    part_index = int(part_str) - 1
                except ValueError:
                    continue
                entry = self.videos_db.get(str(parent_id)) or self.videos_db.get(parent_id)
                if entry and entry.get('files') and len(entry['files']) > part_index:
                    video_file = entry['files'][part_index]
                    if os.path.exists(video_file):
                        try:
                            os.startfile(video_file)
                            self.log_info(f"Ouverture de la vidéo (Part {part_index+1}): {video_file}")
                        except Exception as e:
                            self.log_error(f"Erreur à l'ouverture de la vidéo (Part {part_index+1}): {str(e)}")
                    else:
                        self.log_error(f"Fichier vidéo introuvable pour {parent_id} (Part {part_index+1}).")
                else:
                    self.log_info(f"Aucune vidéo associée pour {parent_id} (Part {part_index+1}).")
            else:
                # Parent row: Open first file
                video_id = self.videos_tree.item(item)['values'][0]
                entry = self.videos_db.get(str(video_id)) or self.videos_db.get(video_id)
                if entry and entry.get('files'):
                    video_file = entry['files'][0]
                    if os.path.exists(video_file):
                        try:
                            os.startfile(video_file)
                            self.log_info(f"Ouverture de la vidéo: {video_file}")
                        except Exception as e:
                            self.log_error(f"Erreur à l'ouverture de la vidéo: {str(e)}")
                    else:
                        self.log_error(f"Fichier vidéo introuvable pour l'enregistrement {video_id}.")
                else:
                    self.log_info(f"Aucune vidéo associée à l'enregistrement {video_id}.")

    def delete_selected_video(self, event=None):
        selections = self.videos_tree.selection()
        for item in selections:
            if "_part_" in item:
                # Child row deletion: remove individual part
                parent_id, part_str = item.split("_part_")
                try:
                    part_index = int(part_str) - 1
                except ValueError:
                    continue
                entry = self.videos_db.get(str(parent_id)) or self.videos_db.get(parent_id)
                if entry and entry.get('files') and len(entry['files']) > part_index:
                    video_file = entry['files'][part_index]
                    if os.path.exists(video_file):
                        try:
                            os.remove(video_file)
                            self.log_info(f"Fichier supprimé: {video_file}")
                        except Exception as e:
                            self.log_error(f"Erreur lors de la suppression de {video_file}: {str(e)}")
                    # Remove the part from the parent's file list
                    entry['files'].pop(part_index)
                    # Update parts count in parent's record
                    entry['parts'] = len(entry.get('files', []))
                else:
                    self.log_info(f"Aucun fichier associé pour {parent_id} (Part {part_index+1}).")
            else:
                # Parent row deletion: remove entire entry and all associated files
                video_id = self.videos_tree.item(item)['values'][0]
                entry = self.videos_db.get(str(video_id)) or self.videos_db.get(video_id)
                if entry:
                    files = entry.get('files', [])
                    for video_file in files:
                        if os.path.exists(video_file):
                            try:
                                os.remove(video_file)
                                self.log_info(f"Fichier supprimé: {video_file}")
                            except Exception as e:
                                self.log_error(f"Erreur lors de la suppression de {video_file}: {str(e)}")
                    self.videos_db.pop(str(video_id), None)
                    self.videos_db.pop(video_id, None)
        self.save_videos_db()
        self.refresh_videos_list()
        self.log_info("Enregistrements sélectionnés supprimés.")

    def add_video_to_db(self, project_id: str, title: str, output_files: list):
        """Add a new video entry to the database"""
        total_duration = 0
        for video_file in output_files:
            if os.path.exists(video_file):
                try:
                    from moviepy.editor import VideoFileClip
                    with VideoFileClip(video_file) as clip:
                        total_duration += clip.duration
                except Exception as e:
                    self.log_error(f"Failed to load file {video_file}: {e}")
                    total_duration = 0
                    break # Stop loading other files from list

        video_data = {
            'title': title,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'status': 'Generated',
            'length': humanize.precisedelta(total_duration),
            'parts': len(output_files),
            'files': output_files
        }

        self.videos_db[project_id] = video_data
        self.save_videos_db()
        self.master.after(0, self.refresh_videos_list)

    def add_subreddit(self):
        new_sub = self.new_subreddit_var.get().strip()
        if new_sub:
            current_subs = self.settings.get("subreddits", [])
            if new_sub not in current_subs:
                current_subs.append(new_sub)
                self.settings["subreddits"] = current_subs
                save_settings(self.settings)
                self.subreddit_dropdown['values'] = current_subs
                self.new_subreddit_var.set("")
                self.log_info(f"Added new subreddit: {new_sub}")

    def update_progress(self, progress: int, message: str = None):
        """Update progress bars based on video writing progress"""
        self.writing_progress = progress
        self.master.after(0, lambda: self.part_progress.config(value=progress))  # Changed from segment_progress
        if message:
            self.master.after(0, lambda: self.set_status(message, "info"))
            # Extract part information from message if available
            if "part" in message.lower():
                self.master.after(0, lambda: self.part_label.config(text=message))  # Update part label

    def setup_logging(self):
        class QueueHandler(logging.Handler):
            def __init__(self, queue):
                super().__init__()
                self.queue = queue

            def emit(self, record):
                try:
                    self.queue.put(self.format(record))
                except Exception as e:
                    print(f"Logging exception: {e}")

        # Remove existing handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Add queue handler
        queue_handler = QueueHandler(log_queue)
        queue_handler.setFormatter(logging.Formatter('%(message)s'))
        root_logger.addHandler(queue_handler)
        root_logger.setLevel(logging.INFO)

    def copy_selection(self, event=None):
        """Copy selected row data to clipboard"""
        selection = self.videos_tree.selection()
        if not selection:
            return
        
        # Get all values from selected row
        values = self.videos_tree.item(selection[0])['values']
        if values:
            text = '\t'.join(str(v) for v in values)
            self.master.clipboard_clear()
            self.master.clipboard_append(text)
            self.log_info("Copied row to clipboard")

if __name__ == "__main__":
    root = tk.Tk()  # Use tk.Tk() instead of ThemedTk
    app = GuiApp(root)
    root.mainloop()
