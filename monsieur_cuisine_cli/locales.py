"""Website locales and their WordPress language codes.

Refresh this mapping with ``python3 support/scripts/update_locales.py``.
"""

LOCALE_SITE_CODES = {
    'bg-BG': 'bg',
    'cs-CZ': 'cs',
    'de-DE': 'de',
    'el-GR': 'el',
    'en-US': 'en',
    'es-ES': 'es',
    'fi-FI': 'fi',
    'fr-FR': 'fr',
    'hr-HR': 'hr',
    'hu-HU': 'hu',
    'it-IT': 'it',
    'nl-NL': 'nl',
    'pl-PL': 'pl',
    'pt-PT': 'pt-pt',
    'ro-RO': 'ro',
    'sk-SK': 'sk',
    'sr-RS': 'sr',
    'sv-SE': 'sv',
}

SUPPORTED_LOCALES = tuple(LOCALE_SITE_CODES)

# Localized, human-readable labels accepted in cookbook Recipe tables. English
# API property names remain accepted for backwards compatibility.
RECIPE_FIELD_LABELS = {
    'bg-BG': {'languageLocale': 'Език', 'deviceTypeIds': 'Тип уред', 'servings': 'Порции', 'recipeId': 'ID на рецепта', 'ingredientGroupName': 'Група продукти', 'preparationTime': 'Време за приготвяне', 'readyInTime': 'Общо време', 'categoryIds': 'Категории', 'complexityId': 'Сложност', 'hintsAndTips': 'Съвети', 'nutrients': 'Хранителни стойности', 'thumbnail': 'Миниатюра', 'detailsImage': 'Снимка на рецептата'},
    'cs-CZ': {'languageLocale': 'Jazyk', 'deviceTypeIds': 'Typ zařízení', 'servings': 'Porce', 'recipeId': 'ID receptu', 'ingredientGroupName': 'Skupina ingrediencí', 'preparationTime': 'Doba přípravy', 'readyInTime': 'Celkový čas', 'categoryIds': 'Kategorie', 'complexityId': 'Náročnost', 'hintsAndTips': 'Tipy', 'nutrients': 'Nutriční hodnoty', 'thumbnail': 'Náhled', 'detailsImage': 'Fotografie receptu'},
    'de-DE': {'languageLocale': 'Sprache', 'deviceTypeIds': 'Gerätetyp', 'servings': 'Portionen', 'recipeId': 'Rezept-ID', 'ingredientGroupName': 'Zutatengruppe', 'preparationTime': 'Vorbereitungszeit', 'readyInTime': 'Gesamtzeit', 'categoryIds': 'Kategorien', 'complexityId': 'Schwierigkeit', 'hintsAndTips': 'Tipps', 'nutrients': 'Nährwerte', 'thumbnail': 'Vorschaubild', 'detailsImage': 'Rezeptbild'},
    'el-GR': {'languageLocale': 'Γλώσσα', 'deviceTypeIds': 'Τύπος συσκευής', 'servings': 'Μερίδες', 'recipeId': 'ID συνταγής', 'ingredientGroupName': 'Ομάδα υλικών', 'preparationTime': 'Χρόνος προετοιμασίας', 'readyInTime': 'Συνολικός χρόνος', 'categoryIds': 'Κατηγορίες', 'complexityId': 'Δυσκολία', 'hintsAndTips': 'Συμβουλές', 'nutrients': 'Διατροφικά στοιχεία', 'thumbnail': 'Μικρογραφία', 'detailsImage': 'Φωτογραφία συνταγής'},
    'en-US': {'languageLocale': 'Language', 'deviceTypeIds': 'Device type', 'servings': 'Servings', 'recipeId': 'Recipe ID', 'ingredientGroupName': 'Ingredient group', 'preparationTime': 'Preparation time', 'readyInTime': 'Total time', 'categoryIds': 'Categories', 'complexityId': 'Difficulty', 'hintsAndTips': 'Tips', 'nutrients': 'Nutrition', 'thumbnail': 'Thumbnail', 'detailsImage': 'Recipe photo'},
    'es-ES': {'languageLocale': 'Idioma', 'deviceTypeIds': 'Tipo de dispositivo', 'servings': 'Raciones', 'recipeId': 'ID de receta', 'ingredientGroupName': 'Grupo de ingredientes', 'preparationTime': 'Tiempo de preparación', 'readyInTime': 'Tiempo total', 'categoryIds': 'Categorías', 'complexityId': 'Dificultad', 'hintsAndTips': 'Consejos', 'nutrients': 'Información nutricional', 'thumbnail': 'Miniatura', 'detailsImage': 'Foto de la receta'},
    'fi-FI': {'languageLocale': 'Kieli', 'deviceTypeIds': 'Laitetyyppi', 'servings': 'Annokset', 'recipeId': 'Reseptin tunnus', 'ingredientGroupName': 'Ainesosaryhmä', 'preparationTime': 'Valmisteluaika', 'readyInTime': 'Kokonaisaika', 'categoryIds': 'Kategoriat', 'complexityId': 'Vaikeustaso', 'hintsAndTips': 'Vinkit', 'nutrients': 'Ravintosisältö', 'thumbnail': 'Pikkukuva', 'detailsImage': 'Reseptikuva'},
    'fr-FR': {'languageLocale': 'Langue', 'deviceTypeIds': 'Type d’appareil', 'servings': 'Personnes', 'recipeId': 'ID de recette', 'ingredientGroupName': 'Groupe d’ingrédients', 'preparationTime': 'Temps de préparation', 'readyInTime': 'Temps total', 'categoryIds': 'Catégories', 'complexityId': 'Difficulté', 'hintsAndTips': 'Conseils', 'nutrients': 'Valeurs nutritionnelles', 'thumbnail': 'Vignette', 'detailsImage': 'Photo de la recette'},
    'hr-HR': {'languageLocale': 'Jezik', 'deviceTypeIds': 'Vrsta uređaja', 'servings': 'Porcije', 'recipeId': 'ID recepta', 'ingredientGroupName': 'Skupina sastojaka', 'preparationTime': 'Vrijeme pripreme', 'readyInTime': 'Ukupno vrijeme', 'categoryIds': 'Kategorije', 'complexityId': 'Zahtjevnost', 'hintsAndTips': 'Savjeti', 'nutrients': 'Nutritivne vrijednosti', 'thumbnail': 'Sličica', 'detailsImage': 'Fotografija recepta'},
    'hu-HU': {'languageLocale': 'Nyelv', 'deviceTypeIds': 'Készüléktípus', 'servings': 'Adagok', 'recipeId': 'Receptazonosító', 'ingredientGroupName': 'Hozzávalócsoport', 'preparationTime': 'Előkészítési idő', 'readyInTime': 'Teljes idő', 'categoryIds': 'Kategóriák', 'complexityId': 'Nehézség', 'hintsAndTips': 'Tippek', 'nutrients': 'Tápérték', 'thumbnail': 'Bélyegkép', 'detailsImage': 'Receptfotó'},
    'it-IT': {'languageLocale': 'Lingua', 'deviceTypeIds': 'Tipo di dispositivo', 'servings': 'Porzioni', 'recipeId': 'ID ricetta', 'ingredientGroupName': 'Gruppo ingredienti', 'preparationTime': 'Tempo di preparazione', 'readyInTime': 'Tempo totale', 'categoryIds': 'Categorie', 'complexityId': 'Difficoltà', 'hintsAndTips': 'Consigli', 'nutrients': 'Valori nutrizionali', 'thumbnail': 'Miniatura', 'detailsImage': 'Foto della ricetta'},
    'nl-NL': {'languageLocale': 'Taal', 'deviceTypeIds': 'Apparaattype', 'servings': 'Porties', 'recipeId': 'Recept-ID', 'ingredientGroupName': 'Ingrediëntengroep', 'preparationTime': 'Voorbereidingstijd', 'readyInTime': 'Totale tijd', 'categoryIds': 'Categorieën', 'complexityId': 'Moeilijkheid', 'hintsAndTips': 'Tips', 'nutrients': 'Voedingswaarden', 'thumbnail': 'Miniatuur', 'detailsImage': 'Receptfoto'},
    'pl-PL': {'languageLocale': 'Język', 'deviceTypeIds': 'Typ urządzenia', 'servings': 'Porcje', 'recipeId': 'ID przepisu', 'ingredientGroupName': 'Grupa składników', 'preparationTime': 'Czas przygotowania', 'readyInTime': 'Całkowity czas', 'categoryIds': 'Kategorie', 'complexityId': 'Trudność', 'hintsAndTips': 'Wskazówki', 'nutrients': 'Wartości odżywcze', 'thumbnail': 'Miniatura', 'detailsImage': 'Zdjęcie przepisu'},
    'pt-PT': {'languageLocale': 'Idioma', 'deviceTypeIds': 'Tipo de aparelho', 'servings': 'Doses', 'recipeId': 'ID da receita', 'ingredientGroupName': 'Grupo de ingredientes', 'preparationTime': 'Tempo de preparação', 'readyInTime': 'Tempo total', 'categoryIds': 'Categorias', 'complexityId': 'Dificuldade', 'hintsAndTips': 'Dicas', 'nutrients': 'Informação nutricional', 'thumbnail': 'Miniatura', 'detailsImage': 'Fotografia da receita'},
    'ro-RO': {'languageLocale': 'Limbă', 'deviceTypeIds': 'Tipul aparatului', 'servings': 'Porții', 'recipeId': 'ID rețetă', 'ingredientGroupName': 'Grup de ingrediente', 'preparationTime': 'Timp de preparare', 'readyInTime': 'Timp total', 'categoryIds': 'Categorii', 'complexityId': 'Dificultate', 'hintsAndTips': 'Sfaturi', 'nutrients': 'Valori nutriționale', 'thumbnail': 'Miniatură', 'detailsImage': 'Fotografia rețetei'},
    'sk-SK': {'languageLocale': 'Jazyk', 'deviceTypeIds': 'Typ zariadenia', 'servings': 'Porcie', 'recipeId': 'ID receptu', 'ingredientGroupName': 'Skupina ingrediencií', 'preparationTime': 'Čas prípravy', 'readyInTime': 'Celkový čas', 'categoryIds': 'Kategórie', 'complexityId': 'Náročnosť', 'hintsAndTips': 'Tipy', 'nutrients': 'Výživové hodnoty', 'thumbnail': 'Miniatúra', 'detailsImage': 'Fotografia receptu'},
    'sr-RS': {'languageLocale': 'Jezik', 'deviceTypeIds': 'Tip uređaja', 'servings': 'Porcije', 'recipeId': 'ID recepta', 'ingredientGroupName': 'Grupa sastojaka', 'preparationTime': 'Vreme pripreme', 'readyInTime': 'Ukupno vreme', 'categoryIds': 'Kategorije', 'complexityId': 'Težina', 'hintsAndTips': 'Saveti', 'nutrients': 'Nutritivne vrednosti', 'thumbnail': 'Sličica', 'detailsImage': 'Fotografija recepta'},
    'sv-SE': {'languageLocale': 'Språk', 'deviceTypeIds': 'Enhetstyp', 'servings': 'Portioner', 'recipeId': 'Recept-ID', 'ingredientGroupName': 'Ingrediensgrupp', 'preparationTime': 'Förberedelsetid', 'readyInTime': 'Total tid', 'categoryIds': 'Kategorier', 'complexityId': 'Svårighetsgrad', 'hintsAndTips': 'Tips', 'nutrients': 'Näringsvärden', 'thumbnail': 'Miniatyrbild', 'detailsImage': 'Receptfoto'},
}
