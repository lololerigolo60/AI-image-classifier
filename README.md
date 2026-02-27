**INSTALLATION**
For Windows
You must have Python installed and ollama. With Ollama, load a vision model: I use Ministral3:3b, which is lightweight and efficient.
Unzip the archive wherever you want.
Run the run.bat file:
Open the console in the directory where you unzipped the file and type
“./run.bat”
it creates a virtual environment if necessary and install the missing libraries

update 02/27/26

Major overhaul of data management and user interface:

- Database: Replacement of JSON indexing with an SQLite database (image_index.db) for better performance and data integrity.
- UI: Addition of a preview window (Toplevel) to display the image in large format and detailed metadata.
- AI: Added the ability to regenerate an individual image directly from the preview.
- UX: Improved pagination with direct page number entry and interactive cursor on thumbnails.
- Robustness: Optimized Ollama prompt and strengthened error handling when moving files.
- Cleanup: Removed manual loading/saving of the JSON file, which has become obsolete.


update 02/26/26
Multi-keyword Search Support:

    Refactored the search engine to support multiple keywords separated by spaces.

    Implemented an all() condition logic: the application now filters and displays images only if all entered terms are found within the image metadata (category, AI description, or filename).

    Improved search flexibility, allowing for more precise filtering (e.g., searching "black cat" will only show images containing both "black" and "cat").

Smart Global Selection (Toggle All):

    Upgraded the "Select All" functionality into a smart toggle.

    Logic: If any displayed image is unselected, clicking "Select All" will check all visible items. If all visible items are already selected, clicking it again will deselect them all.

    Integrated real-time synchronization between the UI checkboxes and the global selection set (selected_files).

UI/UX Improvements:

    The selection counter now updates instantly when using the toggle or manual checkboxes.

    Maintained existing pagination and AI processing features without breaking core functionality.
update 02/25/26
Performance Optimizations

    Multi-Threaded Parallelization: The script now uses a ThreadPoolExecutor with 3 simultaneous "workers". This allows sending three images to Ollama at the same time, fully leveraging your graphics card's parallel processing power instead of processing files one by one.

    "Combo" AI Request (JSON): Instead of calling the AI twice per image (once for category, once for description), the system sends a single instruction requesting a JSON object containing both pieces of information. This cuts the latency related to network/model calls in half.

    Optimized Thumbnail Format: Thumbnail size has been reduced from 384x384 to 224x224 pixels. This is the native standard for most Vision models (like Moondream), which speeds up file creation and reduces VRAM consumption during analysis.

🛠 Internal Logic Improvements

    Massive Pre-Caching: At the start of the sorting process, the script uses all available CPU cores to generate thumbnails before the AI even begins its work. This ensures the AI never has to wait for file preparation.

    Robust Renaming Logic: The renaming process now includes automatic special character cleaning (regex) and collision management by adding counters (e.g., _1, _2) to prevent overwriting existing files.

    Real-Time Indexing: The global_image_index.json is saved every 10 processed images, ensuring you don't lose data if the process is accidentally interrupted.

🖥 Interface & Usability

    Improved Visual Feedback: The progress bar and status text now clearly display "Parallel AI Analysis" and the exact count of images being processed in real-time.

    Cache Protection: A safety feature was added to automatically ignore the ai_cache_thumbnails folder during source directory scanning, preventing the AI from trying to classify its own thumbnails.
update 02/24/26 
The core processing engine has been upgraded to handle large image libraries significantly faster using two main strategies:
1. Multi-threaded Image Proxying

Instead of sending original high-resolution files (which are heavy and slow) directly to the LLM, the app now creates 384px thumbnails.

    Parallel Processing: The app uses all available CPU cores (ThreadPoolExecutor) to generate these miniatures simultaneously.

    I/O Efficiency: Processing 50KB files instead of 10MB+ files reduces data transfer bottlenecks to Ollama by over 90%.

2. Persistent AI Caching

A hidden directory (.cache_ai) is now created within your source folder.

    Skip Redundancy: If you restart the app or re-index the same folder, the AI instantly retrieves existing thumbnails instead of regenerating them.

    Manual Control: A "Clear AI Cache" button has been added to the UI to safely delete these temporary files once your sorting is finalized.


 # **User Guide: AI Image Classifier**   

## **Overview**

The **AI Image Classifier** is a desktop application designed to help you manage and organize your image library using local Artificial Intelligence. Powered by **Ollama**, it analyzes the visual content of your files to sort them or make them searchable via keywords, all without uploading your data to the cloud.

---

## **1. Core Configuration**

* **Ollama Model**: Select your preferred AI model from the dropdown menu at the top.
* *Note*: For best performance, use multimodal models (capable of seeing images) such as `llava`, `moondream`, or `qwen-vl`.


* **Source Folder**: Click this button to select the directory containing the images you want to process.
* **Destination Folder**: Select where you want the organized images to go. If not selected, the app will create subfolders within the source directory.
* **Include Subfolders**: Check this box if you want the app to recursively scan all folders inside your source directory.

---

## **2. Feature: Automatic Sorting**

This tab is used to physically organize your files into category-based folders.

* **Smart Rename**: When enabled, the AI generates a relevant filename based on the image content (e.g., `golden_retriever_playing_park.jpg`) before moving it.
* **Manage Categories**:
* **Add**: Type a category name in the input field and click "Add".
* **Remove**: Double-click any category in the list to delete it.


* **Start Sorting**: The AI analyzes each image, determines which category it belongs to, and moves it to the appropriate subfolder.

---

## **3. Feature: Keyword Search & Indexing**

This tab allows you to find specific images using natural language descriptions.

* **Indexing**: Click the **Index** button to let the AI "describe" all your images. This creates a local file (`image_index.json`) that stores descriptions. This step is required before searching.
* **Search**: Type any keyword (e.g., "mountain", "car", "blue") in the search bar. The app will display thumbnails of matching images.
* **Batch Actions**:
* Select images using the checkboxes on the thumbnails.
* Use **Copy Selection** or **Move Selection** to quickly export your search results to a specific folder.



---

## **4. Technical Requirements**

* **Ollama**: The Ollama server must be running on your computer.
* **Python Dependencies**: Requires `customtkinter`, `Pillow`, and the `ollama` Python library.
* **Supported Formats**: `.jpg`, `.jpeg`, and `.png`.

---

## **5. Tips for Success**

* **Performance**: I recommend using Ministral-3:3b, which is very light and very effective.
* **Duplicates**: If a file with the same name exists in the destination, the app will skip the move to prevent data loss.
