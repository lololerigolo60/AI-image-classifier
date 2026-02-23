📑 User Guide: AI images classifier

This application is an AI-powered tool designed to automatically sort and semantically search through your local image library using Ollama's vision models.
🚀 1. Getting Started
Setting Up the Model

    Launch Ollama: Ensure the Ollama service is running on your computer.

    Select Model: Upon startup, the app will automatically detect your installed models.

        Use a Multimodal model (like llava, moondream, or qwen-vl) for best results.

        Click the Refresh (🔄) button if you recently installed a new model.

Selecting Directories

    Source Folder: The directory containing the images you want to organize or search.

    Destination Folder: (Optional) The directory where sorted images will be moved. If left blank, the app will create folders inside the Source directory.

📂 2. Automated Image Sorting

Located under the "Tri Automatique" (Automatic Sorting) tab.

    Manage Categories:

        Add: Type a new category in the entry field and click "Ajouter".

        Remove: Double-click any category in the list to delete it.

    Smart Renaming: Check the "Renommer intelligemment" box if you want the AI to rename files based on a short description of their content (e.g., cat_on_sofa.jpg).

    Start Sorting: Click "Lancer le Tri". The AI will analyze each image and move it into the folder corresponding to the best-matching category.

🔍 3. Semantic Search & Thumbnails

Located under the "Recherche par mots clés" (search with keywords) tab. This feature allows you to find images by describing them, even if the filename is irrelevant.
Step 1: Indexing (Mandatory for first use)

Before searching, you must click "Indexer".

    The AI will "read" and describe every image in your Source folder.

    Persistence: A file named image_index.json is created in your source folder. This saves the descriptions so you don't have to re-index the next time you open the app.

Step 2: Searching

    Enter keywords in the search bar (e.g., "sunset", "blue car", "manga character").

    Click "Chercher".

    The app will display thumbnails of all matching images.

Step 3: Batch Actions

    Select: Check the boxes on the image thumbnails you want to process.

    Copy/Move: Click "Copier Sélection" or "Déplacer Sélection" to send the chosen images to your Destination folder.

🛠 4. Troubleshooting

    Model not loading: Ensure Ollama is running (ollama serve) and that you have downloaded a vision model (ollama run llava).

    Slow Search: Ensure you have clicked "Indexer" at least once. Searching without an index is not possible.

    Missing Thumbnails: Ensure the Pillow library is installed (pip install Pillow).
