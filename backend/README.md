# Mira AI Agent – Backend

**Mira** is an AI-powered interior design assistant built to help users explore and visualize custom design sketches based on natural language input. This repository contains the backend API logic, image retrieval system, multilingual support, and intelligent query handling for the Mira platform.

#Features

- **Smart Image/Drawing Search**  
  Matches user descriptions to scanned hand-drawn sketches using OpenCLIP and BLIP embeddings.

- **Showroom Information**  
  Instantly provides location, contact, and product details from Bixio Design showrooms.

- **Multilingual Support**  
  Accepts queries in English or Italian, responds accordingly, and translates image captions.

- **Context-Aware Follow-Up**  
  Supports price-related follow-ups based on previous image search results.

- **Voice + Visual Integration** *(via frontend)*  
  Integrates with a speaking digital avatar using D-ID (handled in the frontend).

------

- FastAPI – Lightweight, high-performance backend API
- OpenCLIP + BLIP – For image/text embedding and captioning
- Google Drive API– Stores and retrieves categorized sketches
- D-ID API – Avatar video generation (via frontend)
- Session Memory – Tracks user context 



