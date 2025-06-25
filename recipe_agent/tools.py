from typing import Annotated

import rigging as rg


@rg.tool
async def validate_ingredient_gluten_free(
    ingredient: Annotated[str, "The ingredient name to check for gluten content"],
) -> str:
    """Validates if a specific ingredient is gluten-free and provides details about potential gluten content."""
    ingredient_lower = ingredient.lower().strip()

    # Common gluten-containing ingredients
    gluten_ingredients = {
        "wheat": "Contains gluten - wheat is a primary source of gluten",
        "barley": "Contains gluten - barley contains gluten proteins",
        "rye": "Contains gluten - rye contains gluten proteins",
        "spelt": "Contains gluten - spelt is a wheat variety",
        "kamut": "Contains gluten - kamut is an ancient wheat variety",
        "triticale": "Contains gluten - hybrid of wheat and rye",
        "flour": "May contain gluten - check if labeled as gluten-free flour",
        "bread crumbs": "Likely contains gluten - usually made from wheat bread",
        "soy sauce": "Often contains gluten - many soy sauces contain wheat",
    }

    # Check for direct matches
    for gluten_item, warning in gluten_ingredients.items():
        if gluten_item in ingredient_lower:
            return f"WARNING - {ingredient}: {warning}"

    # Common gluten-free ingredients
    gluten_free_ingredients = {
        "rice",
        "corn",
        "quinoa",
        "buckwheat",
        "millet",
        "amaranth",
        "tapioca",
        "potato",
        "coconut",
        "almond",
        "banana",
        "egg",
        "milk",
        "butter",
        "oil",
        "sugar",
        "honey",
        "maple syrup",
        "vanilla",
        "cinnamon",
        "salt",
        "baking soda",
    }

    for gf_item in gluten_free_ingredients:
        if gf_item in ingredient_lower:
            return f"SAFE - {ingredient}: Naturally gluten-free ingredient"

    return f"VERIFY - {ingredient}: Check product labeling for gluten-free certification"


@rg.tool
async def suggest_gluten_free_flour_substitute(
    original_flour: Annotated[str, "The original flour type that needs substitution"],
    recipe_type: Annotated[str, "Type of recipe (e.g., bread, cake, muffin)"] = "bread",
) -> str:
    """Suggests appropriate gluten-free flour substitutes for different types of baking."""

    substitutes = {
        "all-purpose": {
            "bread": "Gluten-free all-purpose flour blend (1:1 ratio) + 1 tsp xanthan gum per cup",
            "cake": "Gluten-free flour blend or mix of rice flour + potato starch",
            "muffin": "Almond flour + oat flour blend or gluten-free all-purpose flour",
        },
        "wheat": {
            "bread": "Gluten-free bread flour blend or all-purpose GF flour + xanthan gum",
            "cake": "Rice flour + tapioca starch + potato starch blend",
            "muffin": "Oat flour + almond flour combination",
        },
        "bread": {
            "bread": "Gluten-free bread flour blend with xanthan gum already included",
            "cake": "Lighter GF flour blend with rice flour base",
            "muffin": "Gluten-free flour blend or nut flour combination",
        },
    }

    flour_type = original_flour.lower().replace(" flour", "")
    recipe_type_lower = recipe_type.lower()

    if flour_type in substitutes and recipe_type_lower in substitutes[flour_type]:
        suggestion = substitutes[flour_type][recipe_type_lower]
        return f"SUBSTITUTE - For {original_flour} in {recipe_type}: {suggestion}"

    # Default suggestion
    return f"SUBSTITUTE - For {original_flour}: Use certified gluten-free all-purpose flour blend (1:1 ratio) + add 1 tsp xanthan gum per cup if not included in blend"


@rg.tool
async def calculate_recipe_nutrition_estimate(
    servings: Annotated[int, "Number of servings the recipe makes"],
    main_ingredients: Annotated[str, "Comma-separated list of main ingredients with quantities"],
) -> str:
    """Provides rough nutritional estimates for gluten-free baked goods per serving."""

    ingredient_calories = {
        "banana": 105,
        "egg": 70,
        "butter": 100,
        "oil": 120,
        "flour": 95,
        "sugar": 50,
        "honey": 60,
        "maple syrup": 50,
        "nuts": 85,
        "milk": 15,
    }

    total_estimated_calories = 0
    ingredients_found = []

    ingredients = [ing.strip().lower() for ing in main_ingredients.split(",")]

    for ingredient in ingredients:
        for key, calories in ingredient_calories.items():
            if key in ingredient:
                total_estimated_calories += calories
                ingredients_found.append(key)
                break

    if total_estimated_calories == 0:
        return "NUTRITION - Unable to estimate nutrition - no recognized ingredients found"

    calories_per_serving = total_estimated_calories // servings if servings > 0 else 0

    return (
        f"NUTRITION - Estimated nutrition per serving ({servings} servings total):\n"
        f"   - Calories: approximately {calories_per_serving}\n"
        f"   - Based on: {', '.join(ingredients_found)}\n"
        f"   - Note: This is a rough estimate for planning purposes"
    )


BASIC_TOOLS = [
    validate_ingredient_gluten_free,
    suggest_gluten_free_flour_substitute,
]

ALL_TOOLS = [
    validate_ingredient_gluten_free,
    suggest_gluten_free_flour_substitute,
    calculate_recipe_nutrition_estimate,
]
