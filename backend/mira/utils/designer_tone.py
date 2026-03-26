def designer_message(intent: str, lang: str, query: str, results: list) -> str:
    # Basic “designer voice” templates with actionable follow-ups.
    top_caption = ""
    if results and isinstance(results, list) and isinstance(results[0], dict):
        top_caption = results[0].get("caption") or ""

    if intent == "search":
        if lang == "it":
            return (
                f"Perfetto  per {query} ho selezionato alcune proposte vicine al tuo stile.\n"
                f"La più coerente sembra: {top_caption}.\n\n"
                # "Dimmi cosa vuoi ottimizzare:\n"
                # "1) più **spazio contenitivo** (armadio/guardaroba)\n"
                # "2) più **luce e leggerezza** (linee minimal)\n"
                # "3) più **calore** (legno, texture)\n\n"
                # "👉 Puoi anche dire: **“disegno 2”** per scegliere una proposta."
            )
        return (
            f"Great for **{query}** I picked a few close references.\n"
            f"The closest one looks like: **{top_caption}**.\n\n"
            # "What would you like to improve?\n"
            # "1) more **storage** (wardrobe/closet)\n"
            # "2) more **light/minimal lines**\n"
            # "3) more **warmth** (wood/texture)\n\n"
            # "👉 You can also say: **“drawing 2”** to select one."
        )

    if intent == "select":
        return (
            "Hai selezionato il disegno. Che modifica vuoi fare? (es. “aggiungi armadio a sinistra”, “sposta il letto”, “più mensole”)."
            if lang == "it"
            else "You selected the drawing. What would you like to change? (e.g., “add a wardrobe on the left”, “move the bed”, “more shelves”)."
        )

    if intent == "modify":
        return (
            "Fatto ✅ Ho applicato la modifica come bozza. Vuoi che lo rendiamo più minimal o più caldo (legno/texture)?"
            if lang == "it"
            else "Done ✅ I applied the change as a draft. Do you want it more minimal or more warm(wood/texture)?"
        )

    if intent == "follow_up_cost":
        return (
            "Posso darti una stima indicativa se mi dici misure e materiali (es. teak/laccato, ante scorrevoli o battenti). "
            "Il preventivo finale va confermato con il team."
            if lang == "it"
            else "I can give a rough estimate if you share measurements and materials (e.g., teak/lacquer, sliding or hinged doors). Final quote must be confirmed by the team."
        )

    # fallback
    return (
        "Mi aiuti a capire meglio? Descrivi lo stile (moderno/classico/minimal) e 1–2 elementi chiave (letto, armadio, luci)."
        if lang == "it"
        else "Help me understand: what style (modern/classic/minimal) and 1–2 key elements (bed, wardrobe, lighting)?"
    )
