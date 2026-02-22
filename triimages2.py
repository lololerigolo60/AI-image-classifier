import os
import shutil
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
import ollama

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class ImageSorterApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AI_image_classifier")
        self.geometry("800x750")

        self.target_dir = ""
        self.categories = [
            "realism", "comics", "manga", "painting", "watercolor",
            "sport", "urban city", "retro and vintage", "sketch", "portrait",
            "landscape", "architecture", "interior", "fauna", "flora",
            "space", "vehicles", "cyberpunk", "fantasy", "science fiction",
            "steampunk", "horror", "abstract", "minimalism", "caricatures"
        ]

        # --- UI Layout ---
        self.grid_columnconfigure(0, weight=1)

        # Sélection du Modèle
        self.model_frame = ctk.CTkFrame(self)
        self.model_frame.pack(pady=15, padx=20, fill="x")
        ctk.CTkLabel(self.model_frame, text="Modèle Ollama :", font=("Arial", 12, "bold")).pack(side="left", padx=10)

        self.model_var = ctk.StringVar(value="Chargement des modèles...")
        self.combo_models = ctk.CTkComboBox(self.model_frame, variable=self.model_var, width=250, state="disabled")
        self.combo_models.pack(side="left", padx=5, fill="x", expand=True)

        self.btn_refresh = ctk.CTkButton(self.model_frame, text="🔄", width=40, command=self.refresh_models_thread)
        self.btn_refresh.pack(side="left", padx=10)

        # Sélection du Dossier
        self.btn_browse = ctk.CTkButton(self, text="Sélectionner le dossier d'images", command=self.browse_folder)
        self.btn_browse.pack(pady=10)
        self.lbl_path = ctk.CTkLabel(self, text="Aucun dossier sélectionné", font=("Arial", 10, "italic"), text_color="gray")
        self.lbl_path.pack()

        # Gestion des Catégories
        self.cat_frame = ctk.CTkFrame(self)
        self.cat_frame.pack(pady=10, padx=20, fill="both", expand=True)

        ctk.CTkLabel(self.cat_frame, text="Catégories (Double-cliquez pour supprimer)", font=("Arial", 12)).pack(pady=5)

        self.entry_frame = ctk.CTkFrame(self.cat_frame, fg_color="transparent")
        self.entry_frame.pack(fill="x", padx=10, pady=5)
        self.entry_cat = ctk.CTkEntry(self.entry_frame, placeholder_text="Nouvelle catégorie...")
        self.entry_cat.pack(side="left", padx=5, fill="x", expand=True)
        ctk.CTkButton(self.entry_frame, text="Ajouter", width=80, command=self.add_category).pack(side="right")

        self.listbox_cats = ctk.CTkTextbox(self.cat_frame, height=200, cursor="hand2")
        self.listbox_cats.pack(pady=10, padx=10, fill="both", expand=True)
        self.listbox_cats.bind("<Double-Button-1>", self.on_double_click)
        self.update_listbox()

        # Action
        self.btn_start = ctk.CTkButton(self, text="Lancer le tri automatique", fg_color="#2ecc71", height=45, command=self.start_sorting_thread)
        self.btn_start.pack(pady=20)

        self.progress = ctk.CTkProgressBar(self, width=500)
        self.progress.set(0)
        self.progress.pack(pady=10)

        self.lbl_status = ctk.CTkLabel(self, text="Connexion à Ollama...", font=("Arial", 11))
        self.lbl_status.pack()

        # Chargement initial des modèles en arrière-plan
        self.refresh_models_thread()

    def refresh_models_thread(self):
        """Lance le chargement des modèles dans un thread séparé pour ne pas bloquer l'UI."""
        self.btn_refresh.configure(state="disabled")
        self.combo_models.configure(state="disabled")
        self.model_var.set("Chargement des modèles...")
        self.lbl_status.configure(text="Connexion à Ollama...", text_color="gray")
        threading.Thread(target=self._fetch_models, daemon=True).start()

    def _fetch_models(self):
        """Récupère la liste des modèles installés (exécuté dans un thread)."""
        try:
            models_info = ollama.list()

            # Compatibilité avec les différentes versions de la lib ollama-python
            # Ancienne version : dict avec clé 'models' contenant des dicts
            # Nouvelle version  : objet ListResponse avec attribut 'models' contenant des objets Model
            models_list = (
                models_info.get('models', [])
                if isinstance(models_info, dict)
                else getattr(models_info, 'models', [])
            )

            names = []
            for m in models_list:
                if isinstance(m, dict):
                    name = m.get('name') or m.get('model', '')
                else:
                    name = getattr(m, 'name', None) or getattr(m, 'model', '')
                if name:
                    names.append(name)

            # Retour sur le thread principal pour mettre à jour l'UI
            self.after(0, self._update_model_ui, names, None)

        except Exception as e:
            self.after(0, self._update_model_ui, [], str(e))

    def _update_model_ui(self, names, error):
        """Met à jour la ComboBox et le statut (doit être appelé depuis le thread principal)."""
        self.btn_refresh.configure(state="normal")

        if error:
            self.lbl_status.configure(
                text=f"Erreur de connexion à Ollama : {error}", text_color="red"
            )
            self.model_var.set("Ollama non disponible")
            self.combo_models.configure(state="normal")
            return

        if not names:
            self.lbl_status.configure(text="Aucun modèle Ollama installé.", text_color="orange")
            self.model_var.set("Aucun modèle trouvé")
            self.combo_models.configure(state="normal")
            return

        self.combo_models.configure(values=names, state="normal")

        # Priorité aux modèles multimodaux connus (nécessaires pour analyser des images)
        multimodal_keywords = ["llava", "minicpm-v", "bakllava", "moondream", "cogvlm", "qwen-vl"]
        selected = names[0]
        for keyword in multimodal_keywords:
            for name in names:
                if keyword in name.lower():
                    selected = name
                    break
            else:
                continue
            break

        self.model_var.set(selected)
        self.lbl_status.configure(
            text=f"{len(names)} modèle(s) trouvé(s) — '{selected}' sélectionné",
            text_color="green"
        )

    def browse_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.target_dir = path
            self.lbl_path.configure(text=path, text_color="white")

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
            index = self.listbox_cats.index(f"@{event.x},{event.y}")
            line = index.split('.')[0]
            name = self.listbox_cats.get(f"{line}.0", f"{line}.end").strip()
            if name in self.categories:
                self.categories.remove(name)
                self.update_listbox()
        except:
            pass

    def start_sorting_thread(self):
        if not self.target_dir or not self.categories:
            messagebox.showwarning("Attention", "Sélectionnez un dossier et des catégories.")
            return
        self.btn_start.configure(state="disabled")
        threading.Thread(target=self.run_sorting, daemon=True).start()

    def run_sorting(self):
        for cat in self.categories + ['inconnu']:
            os.makedirs(os.path.join(self.target_dir, cat), exist_ok=True)

        valid_ext = ('.png', '.jpg', '.jpeg', '.webp')
        files = [f for f in os.listdir(self.target_dir) if f.lower().endswith(valid_ext)]

        for i, filename in enumerate(files):
            path = os.path.join(self.target_dir, filename)
            self.lbl_status.configure(text=f"Analyse : {filename}")
            try:
                prompt = f"Categorize this image. Options: {', '.join(self.categories)}. Reply with exactly ONE word."
                response = ollama.generate(
                    model=self.model_var.get(),
                    prompt=prompt,
                    images=[path],
                    stream=False
                )
                result = response['response'].strip().lower()

                found_cat = 'inconnu'
                for cat in self.categories:
                    if cat in result:
                        found_cat = cat
                        break

                shutil.move(path, os.path.join(self.target_dir, found_cat, filename))

            except Exception as e:
                print(f"Erreur sur {filename} : {e}")

            self.progress.set((i + 1) / len(files))

        self.lbl_status.configure(text="Terminé !")
        messagebox.showinfo("Succès", "Tri terminé.")
        self.btn_start.configure(state="normal")
        self.progress.set(0)


if __name__ == "__main__":
    app = ImageSorterApp()

    app.mainloop()
