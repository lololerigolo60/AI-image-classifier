import os
import shutil
import threading
import json
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import ollama
import re

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class ImageSorterApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AI-image-classifier")
        self.geometry("1000x950")

        self.target_dir = ""
        self.dest_dir = "" 
        self.index_data = {} 
        self.found_images = [] 

        self.categories = [
            "realism", "comics", "manga", "painting", "watercolor",
            "sport", "urban city", "retro and vintage", "sketch", "portrait",
            "landscape", "architecture", "interior", "fauna", "flora",
            "space", "vehicles", "cyberpunk", "fantasy", "science fiction",
            "steampunk", "horror", "abstract", "minimalism", "caricatures"
        ]

        # --- UI Layout ---
        self.grid_columnconfigure(0, weight=1)

        # --- BLOC MODÈLE (STRICTEMENT ORIGINAL) ---
        self.model_frame = ctk.CTkFrame(self)
        self.model_frame.pack(pady=15, padx=20, fill="x")
        ctk.CTkLabel(self.model_frame, text="Modèle Ollama :", font=("Arial", 12, "bold")).pack(side="left", padx=10)

        self.model_var = ctk.StringVar(value="Chargement des modèles...")
        self.combo_models = ctk.CTkComboBox(self.model_frame, variable=self.model_var, width=250, state="disabled")
        self.combo_models.pack(side="left", padx=5, fill="x", expand=True)

        self.btn_refresh = ctk.CTkButton(self.model_frame, text="🔄", width=40, command=self.refresh_models_thread)
        self.btn_refresh.pack(side="left", padx=10)

        # --- GESTION DOSSIERS ---
        self.dir_frame = ctk.CTkFrame(self)
        self.dir_frame.pack(pady=10, padx=20, fill="x")
        
        ctk.CTkButton(self.dir_frame, text="Dossier Source", command=self.browse_source).grid(row=0, column=0, padx=10, pady=5)
        self.lbl_status_source = ctk.CTkLabel(self.dir_frame, text="Non sélectionné", font=("Arial", 10, "italic"))
        self.lbl_status_source.grid(row=0, column=1, sticky="w")

        ctk.CTkButton(self.dir_frame, text="Dossier Destination", command=self.browse_dest).grid(row=1, column=0, padx=10, pady=5)
        self.lbl_status_dest = ctk.CTkLabel(self.dir_frame, text="Par défaut : source", font=("Arial", 10, "italic"))
        self.lbl_status_dest.grid(row=1, column=1, sticky="w")

        # --- SYSTÈME D'ONGLETS ---
        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=20, pady=10)
        self.tab_sort = self.tabs.add("Tri Automatique")
        self.tab_search = self.tabs.add("Recherche par mots clés")

        self.setup_sort_tab()
        self.setup_search_tab()

        self.progress = ctk.CTkProgressBar(self, width=600)
        self.progress.set(0)
        self.progress.pack(pady=10)

        self.lbl_status = ctk.CTkLabel(self, text="Connexion à Ollama...", font=("Arial", 11))
        self.lbl_status.pack()

        self.refresh_models_thread()

    # --- TES FONCTIONS ORIGINALES POUR LE MODÈLE (INCHANGÉES) ---
    def refresh_models_thread(self):
        self.btn_refresh.configure(state="disabled")
        self.combo_models.configure(state="disabled")
        self.model_var.set("Chargement des modèles...")
        self.lbl_status.configure(text="Connexion à Ollama...", text_color="gray")
        threading.Thread(target=self._fetch_models, daemon=True).start()

    def _fetch_models(self):
        try:
            models_info = ollama.list()
            models_list = (models_info.get('models', []) if isinstance(models_info, dict) else getattr(models_info, 'models', []))
            names = []
            for m in models_list:
                if isinstance(m, dict): name = m.get('name') or m.get('model', '')
                else: name = getattr(m, 'name', None) or getattr(m, 'model', '')
                if name: names.append(name)
            self.after(0, self._update_model_ui, names, None)
        except Exception as e:
            self.after(0, self._update_model_ui, [], str(e))

    def _update_model_ui(self, names, error):
        self.btn_refresh.configure(state="normal")
        if error:
            self.lbl_status.configure(text=f"Erreur : {error}", text_color="red")
            self.model_var.set("Ollama non disponible")
            self.combo_models.configure(state="normal")
            return
        if not names:
            self.lbl_status.configure(text="Aucun modèle trouvé.", text_color="orange")
            self.model_var.set("Aucun modèle trouvé")
            self.combo_models.configure(state="normal")
            return
        self.combo_models.configure(values=names, state="normal")
        multimodal_keywords = ["llava", "minicpm-v", "bakllava", "moondream", "cogvlm", "qwen-vl"]
        selected = names[0]
        for keyword in multimodal_keywords:
            for name in names:
                if keyword in name.lower():
                    selected = name
                    break
            else: continue
            break
        self.model_var.set(selected)
        self.lbl_status.configure(text=f"{len(names)} modèle(s) trouvé(s)", text_color="green")

    # --- INTERFACE TRI (AVEC AJOUT/SUPPRESSION CATÉGORIES) ---
    def setup_sort_tab(self):
        self.rename_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(self.tab_sort, text="Renommer intelligemment via l'IA", variable=self.rename_var).pack(pady=10)

        # Ajout de catégorie
        self.entry_frame = ctk.CTkFrame(self.tab_sort, fg_color="transparent")
        self.entry_frame.pack(fill="x", padx=20, pady=5)
        self.entry_cat = ctk.CTkEntry(self.entry_frame, placeholder_text="Nouvelle catégorie...")
        self.entry_cat.pack(side="left", padx=5, fill="x", expand=True)
        ctk.CTkButton(self.entry_frame, text="Ajouter", width=80, command=self.add_category).pack(side="right")

        # Liste des catégories
        ctk.CTkLabel(self.tab_sort, text="Catégories (Double-clic pour supprimer) :", font=("Arial", 11)).pack(pady=2)
        self.listbox_cats = ctk.CTkTextbox(self.tab_sort, height=180, cursor="hand2")
        self.listbox_cats.pack(fill="both", expand=True, padx=20, pady=5)
        self.listbox_cats.bind("<Double-Button-1>", self.on_double_click)
        self.update_listbox()

        self.btn_start = ctk.CTkButton(self.tab_sort, text="Lancer le Tri", fg_color="#2ecc71", height=40, command=self.start_sorting_thread)
        self.btn_start.pack(pady=15)

    # --- GESTION CATÉGORIES ---
    def update_listbox(self):
        self.listbox_cats.configure(state="normal")
        self.listbox_cats.delete("1.0", "end")
        for cat in self.categories:
            self.listbox_cats.insert("end", f"{cat}\n")
        self.listbox_cats.configure(state="disabled")

    def add_category(self):
        cat = self.entry_cat.get().strip().lower()
        if cat and cat not in self.categories:
            self.categories.append(cat)
            self.update_listbox()
            self.entry_cat.delete(0, 'end')

    def on_double_click(self, event):
        try:
            line = self.listbox_cats.index(f"@{event.x},{event.y}").split('.')[0]
            name = self.listbox_cats.get(f"{line}.0", f"{line}.end").strip()
            if name in self.categories:
                self.categories.remove(name)
                self.update_listbox()
        except: pass

    # --- INTERFACE RECHERCHE ---
    def setup_search_tab(self):
        f = ctk.CTkFrame(self.tab_search)
        f.pack(fill="x", padx=10, pady=10)
        self.entry_query = ctk.CTkEntry(f, placeholder_text="Mots-clés...")
        self.entry_query.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkButton(f, text="Chercher", width=80, command=self.run_search).pack(side="left", padx=2)
        ctk.CTkButton(f, text="Indexer", width=80, command=self.start_indexing_thread).pack(side="left", padx=2)

        self.search_scroll = ctk.CTkScrollableFrame(self.tab_search, label_text="Résultats")
        self.search_scroll.pack(fill="both", expand=True, padx=10, pady=10)
        self.search_scroll.columnconfigure((0,1,2,3), weight=1)

        act = ctk.CTkFrame(self.tab_search)
        act.pack(fill="x", pady=5)
        ctk.CTkButton(act, text="Copier Sélection", command=lambda: self.batch_action("copy")).pack(side="left", padx=20)
        ctk.CTkButton(act, text="Déplacer Sélection", command=lambda: self.batch_action("move"), fg_color="#e67e22").pack(side="left", padx=20)

    # --- LOGIQUE INDEX & RECHERCHE ---
    def load_index(self):
        if not self.target_dir: return
        idx_path = os.path.join(self.target_dir, "image_index.json")
        if os.path.exists(idx_path):
            with open(idx_path, 'r', encoding='utf-8') as f:
                self.index_data = json.load(f)

    def save_index(self):
        if not self.target_dir: return
        idx_path = os.path.join(self.target_dir, "image_index.json")
        with open(idx_path, 'w', encoding='utf-8') as f:
            json.dump(self.index_data, f, indent=4)

    def start_indexing_thread(self):
        if not self.target_dir: return
        threading.Thread(target=self.run_indexing, daemon=True).start()

    def run_indexing(self):
        files = [f for f in os.listdir(self.target_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        for i, f in enumerate(files):
            if f not in self.index_data:
                self.lbl_status.configure(text=f"Indexation : {f}")
                try:
                    res = ollama.generate(model=self.model_var.get(), prompt="Describe image in 10 words", images=[os.path.join(self.target_dir, f)])
                    self.index_data[f] = res['response'].lower()
                except: continue
            self.progress.set((i+1)/len(files))
        self.save_index()
        self.lbl_status.configure(text="Indexation terminée", text_color="green")

    def run_search(self):
        q = self.entry_query.get().lower()
        for w in self.search_scroll.winfo_children(): w.destroy()
        self.found_images = []
        r, c = 0, 0
        for f_name, desc in self.index_data.items():
            if q in desc or q in f_name.lower():
                path = os.path.join(self.target_dir, f_name)
                self.display_thumb(path, r, c)
                c += 1
                if c > 3: c = 0; r += 1

    def display_thumb(self, path, r, c):
        try:
            f = ctk.CTkFrame(self.search_scroll)
            f.grid(row=r, column=c, padx=5, pady=5)
            img = Image.open(path); img.thumbnail((120, 120))
            tk_img = ImageTk.PhotoImage(img)
            l = ctk.CTkLabel(f, image=tk_img, text=""); l.image = tk_img; l.pack()
            v = ctk.BooleanVar()
            ctk.CTkCheckBox(f, text=os.path.basename(path)[:12], variable=v).pack()
            self.found_images.append((path, v))
        except: pass

    def batch_action(self, mode):
        t = self.dest_dir if self.dest_dir else filedialog.askdirectory()
        if not t: return
        for path, v in self.found_images:
            if v.get():
                try:
                    if mode == "copy": shutil.copy(path, t)
                    else: shutil.move(path, t)
                except: pass
        messagebox.showinfo("OK", "Terminé")

    # --- LOGIQUE DE TRI ---
    def start_sorting_thread(self):
        if not self.target_dir: return
        self.btn_start.configure(state="disabled")
        threading.Thread(target=self.run_sorting, daemon=True).start()

    def run_sorting(self):
        final_dest = self.dest_dir if self.dest_dir else self.target_dir
        for cat in self.categories + ['inconnu']: os.makedirs(os.path.join(final_dest, cat), exist_ok=True)
        files = [f for f in os.listdir(self.target_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        for i, f in enumerate(files):
            p = os.path.join(self.target_dir, f)
            self.lbl_status.configure(text=f"Tri : {f}")
            res = ollama.generate(model=self.model_var.get(), prompt=f"Pick ONE category: {self.categories}", images=[p])
            cat = 'inconnu'
            for c in self.categories:
                if c in res['response'].lower(): cat = c; break
            
            new_f = f
            if self.rename_var.get():
                r_res = ollama.generate(model=self.model_var.get(), prompt="5 words description no punctuation", images=[p])
                clean = re.sub(r'[^a-z0-9_]', '', r_res['response'].lower().replace(" ","_"))[:50]
                new_f = f"{clean}{os.path.splitext(f)[1]}"

            try: shutil.move(p, os.path.join(final_dest, cat, new_f))
            except: pass
            self.progress.set((i+1)/len(files))
        
        self.btn_start.configure(state="normal")
        self.lbl_status.configure(text="Tri terminé")

    def browse_source(self):
        p = filedialog.askdirectory()
        if p: 
            self.target_dir = p; self.lbl_status_source.configure(text=p)
            self.load_index()

    def browse_dest(self):
        p = filedialog.askdirectory()
        if p: self.dest_dir = p; self.lbl_status_dest.configure(text=p)

if __name__ == "__main__":
    app = ImageSorterApp()
    app.mainloop()
