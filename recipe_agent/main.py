import os
import typing as t
from dataclasses import dataclass

import backoff
import backoff.types
import cyclopts
import dotenv
import dreadnode as dn
import logfire
import rigging as rg
from loguru import logger
from rigging import Message

from recipe_agent.tools import BASIC_TOOLS
from recipe_agent.utils import calculate_gluten_free_score, extract_recipe_content

logfire.configure()

app = cyclopts.App()


def on_backoff(details: backoff.types.Details) -> None:
    """Handle backoff events for rate limiting."""
    wait = details.get("wait", 0)
    logger.warning(f"Backing off {wait:.2f}s")


# Create backoff wrapper for handling rate limits and API errors
backoff_wrapper = backoff.on_exception(
    backoff.expo,
    (
        Exception,  # Catch all exceptions for robustness
    ),
    max_time=5 * 60,  # 5 minutes
    max_value=240,  # 4 minutes
    on_backoff=on_backoff,
    jitter=backoff.random_jitter,
)


@cyclopts.Parameter(name="*", group="args")
@dataclass
class Args:
    recipe_model: str
    """Model to use for recipe generation"""
    judge_model: str
    """Model to use for gluten-free ingredient evaluation"""
    requester_model: str = ""
    """Model to use for recipe requests (defaults to recipe_model if not specified)"""
    num_requests: int = 1
    """Number of recipe requests to generate and evaluate"""
    enable_caching: bool = True
    """Enable rigging message-level caching for improved performance"""
    enable_tools: bool = False
    """Enable rigging tools for recipe generation agent"""
    max_steps: int = 10
    """Maximum number of steps per agent"""
    log_level: str = "INFO"
    """Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"""


@cyclopts.Parameter(name="*", group="dreadnode")
@dataclass
class DreadnodeArgs:
    server: str = "https://platform.dreadnode.io"
    """Dreadnode server URL"""
    token: str | None = None
    """Dreadnode API token (defaults to $DREADNODE_TOKEN)"""
    project: str = "recipe-agent"
    """Dreadnode project name"""
    console: t.Annotated[bool, cyclopts.Parameter(negative=False)] = False
    """Show span information in the console"""


class RecipeModel(rg.Model):
    recipe: str

    @classmethod
    def xml_tag(cls) -> str:
        return "recipe"

    @classmethod
    def xml_example(cls) -> str:
        return f"<{cls.xml_tag()}>your_complete_recipe_here</{cls.xml_tag()}>"


@dn.task(name="Request Recipe")
async def request_gluten_free_recipe(generator: rg.Generator, enable_caching: bool = True) -> str:
    """Agent that requests a gluten-free banana bread recipe"""
    logger.info("Requesting gluten-free banana bread recipe...")

    message = Message(
        role="user",
        content="Please ask for a gluten-free banana bread recipe. Be specific about wanting it to be gluten-free.",
    )

    if enable_caching:
        try:
            message = message.cache()
        except AttributeError:
            logger.debug("Message caching not supported, skipping cache")

    chat = await generator.wrap(backoff_wrapper).chat(message).run()

    request = chat.last.content
    logger.info(f"Recipe request: {request}")
    return request


@dn.task(name="Generate Recipe")
async def generate_recipe(
    generator: rg.Generator,
    request: str,
    enable_caching: bool = True,
    enable_tools: bool = False,
) -> tuple[str, int]:
    """Agent that generates a banana bread recipe based on request"""
    logger.info("Generating banana bread recipe...")

    tools_instruction = ""
    if enable_tools:
        validate_example = """<tool_call name="validate_ingredient_gluten_free">
  <ingredient>wheat flour</ingredient>
</tool_call>"""

        substitute_example = """<tool_call name="suggest_gluten_free_flour_substitute">
  <original_flour>all-purpose flour</original_flour>
  <recipe_type>bread</recipe_type>
</tool_call>"""

        tools_instruction = f"""

        <tools>
        The following tools are available to you:

        # Validate Ingredient for Gluten-Free Status

        To check if specific ingredients are gluten-free, use the following format:
        {validate_example}

        - The validation will be executed when you finish your response and the result will be sent in the next message
        - Provides detailed warnings about gluten-containing ingredients
        - Identifies naturally gluten-free ingredients
        - Returns safety status and recommendations

        # Suggest Gluten-Free Flour Substitute

        To get recommendations for gluten-free flour alternatives, use the following format:
        {substitute_example}

        - The substitution recommendations will be executed and results sent in the next message
        - Provides specific substitution ratios and additional ingredients needed
        - Considers different recipe types (bread, cake, muffin)
        - Returns detailed substitution instructions
        </tools>

        <guidance>
        - Use the XML tags above to structure your tool calling
        - Always validate flour types and questionable ingredients using the validation tool
        - Use the flour substitute tool when specifying flour in your recipe
        - Call tools to ensure your recipe is truly gluten-free and safe
        - Include tool recommendations in your final recipe
        </guidance>
        """

    system_message = Message(
        role="system",
        content=f"""\
        You are a skilled baker who creates recipes. When asked for a recipe, \
        respond with a complete recipe wrapped in XML tags. \
        Include a title, ingredients list, and step-by-step instructions.{tools_instruction}

        # Recipe Format

        To provide a recipe, place it between these tags:

        {RecipeModel.xml_example()}
        """,
    )

    # Apply caching if enabled and supported
    if enable_caching:
        try:
            system_message = system_message.cache()
        except AttributeError:
            logger.debug("Message caching not supported, skipping cache")

    user_message = Message(role="user", content=f"User request: {request}")

    # Build the pipeline with optional tools and backoff
    pipeline = generator.wrap(backoff_wrapper).chat([system_message, user_message])

    if enable_tools:
        logger.info("Enabling rigging tools for recipe generation")
        pipeline = pipeline.using(
            *BASIC_TOOLS,
            max_depth=3,  # Allow some tool usage
        )

        # Log available tools
        logger.info(f"Tools available: {[tool.__name__ for tool in BASIC_TOOLS]}")

    chat = await pipeline.run()

    # Log the number of messages in the chat for debugging
    logger.debug(f"Chat completed with {len(chat.all)} messages")
    if enable_tools:
        logger.debug(f"Message roles in chat: {[msg.role for msg in chat.all]}")

    tool_calls_made = 0
    if enable_tools:
        tool_calls_found = False

        for message in chat.all:
            if hasattr(message, "tool_calls") and message.tool_calls:
                tool_calls_found = True
                tool_calls_made += len(message.tool_calls)
                logger.info(f"Tool calls made in message: {len(message.tool_calls)}")
                for i, tool_call in enumerate(message.tool_calls, 1):
                    logger.info(f"  Tool call {i}: {tool_call.function.name}")
                    logger.debug(f"    Arguments: {tool_call.function.arguments}")
            elif message.role == "tool":
                tool_calls_found = True
                logger.info(f"Tool response: {message.content[:100]}...")

        if tool_calls_found:
            logger.info(f"Total tool calls made: {tool_calls_made}")
        else:
            logger.info("No tools were called during recipe generation")

    # Try to parse structured recipe, fall back to raw content
    try:
        parsed_recipe = chat.last.try_parse(RecipeModel)
        if parsed_recipe:
            logger.info("Generated structured recipe using rigging model")
            recipe_content = f"<recipe>{parsed_recipe.recipe}</recipe>"
            logger.info(f"Recipe content: {recipe_content}")
            return recipe_content, tool_calls_made
    except (AttributeError, ValueError) as e:
        logger.debug(f"Rigging model parsing failed: {e}")

    recipe = chat.last.content
    tools_status = "with tools" if enable_tools else "without tools"
    logger.info(f"Generated recipe with XML tags ({tools_status})")
    logger.info(f"Recipe content: {recipe}")
    return recipe, tool_calls_made


@dn.task(name="Judge Ingredients")
async def judge_gluten_free_ingredients(
    generator: rg.Generator,
    recipe: str,
    enable_caching: bool = True,
) -> dict[str, t.Any]:
    """Agent that evaluates if recipe ingredients are actually gluten-free"""
    logger.info("Evaluating recipe ingredients for gluten-free compliance...")

    # Extract recipe content from XML tags for analysis
    recipe_content = extract_recipe_content(recipe)

    # Conditionally cache the system prompt for judge agent to optimize repeated calls
    system_message = Message(
        role="system",
        content="""\
        You are a nutritionist expert in gluten-free ingredients. \
        Analyze the given recipe and determine if ALL ingredients are gluten-free. \
        Provide a score from 0-100 where 100 means completely gluten-free. \
        List any problematic ingredients and suggest gluten-free alternatives.
        """,
    )

    # Apply caching if enabled and supported
    if enable_caching:
        try:
            system_message = system_message.cache()
        except AttributeError:
            logger.debug("Message caching not supported, skipping cache")

    user_message = Message(
        role="user",
        content=f"Please evaluate this recipe for gluten-free compliance:\n\n{recipe_content}",
    )

    chat = await generator.wrap(backoff_wrapper).chat([system_message, user_message]).run()

    evaluation = chat.last.content
    logger.info(f"Ingredient evaluation: {evaluation}")

    # Simple scoring based on keywords (in real implementation, could be more sophisticated)
    gluten_free_threshold = 80
    score = calculate_gluten_free_score(recipe_content)

    return {
        "score": score,
        "evaluation": evaluation,
        "is_gluten_free": score >= gluten_free_threshold,
    }


@app.default
async def agent(*, args: Args, dn_args: DreadnodeArgs | None = None) -> None:
    """
    Multi-agent system for gluten-free banana bread recipe generation and evaluation.

    Three agents work together:
    1. Requester: Asks for a gluten-free banana bread recipe
    2. Recipe Generator: Creates the recipe with XML structure
    3. Judge: Evaluates ingredients for gluten-free compliance
    """

    dotenv.load_dotenv()

    logger.enable("rigging")

    dn_args = dn_args or DreadnodeArgs()

    token = dn_args.token or os.getenv("DREADNODE_TOKEN")

    dn.configure(
        server=dn_args.server,
        token=token,
        project=dn_args.project,
        console=dn_args.console,
    )

    requester_model = args.requester_model or args.recipe_model

    # Create meaningful run name and tags based on configuration
    run_name = f"recipe-agent-{args.num_requests}reqs"
    if args.enable_tools:
        run_name += "-tools"

    # Build tags for categorization and filtering
    run_tags = ["multi-agent", "recipe-generation", "gluten-free"]
    if args.enable_tools:
        run_tags.append("tools-enabled")
    if args.enable_caching:
        run_tags.append("caching-enabled")
    if args.num_requests > 1:
        run_tags.append("batch-processing")

    # Determine primary model provider for attributes
    primary_provider = args.recipe_model.split("-")[0] if "-" in args.recipe_model else "unknown"

    with (
        dn.run(
            name=run_name,
            tags=run_tags,
            model_provider=primary_provider,
            batch_size=args.num_requests,
            tools_enabled=args.enable_tools,
            caching_enabled=args.enable_caching,
        ),
        dn.task_span("Recipe Agent System"),
    ):
        dn.log_params(
            recipe_model=args.recipe_model,
            judge_model=args.judge_model,
            requester_model=requester_model,
            num_requests=args.num_requests,
            enable_caching=args.enable_caching,
            enable_tools=args.enable_tools,
            max_steps=args.max_steps,
        )

        requester_gen = rg.get_generator(requester_model)
        recipe_gen = rg.get_generator(args.recipe_model)
        judge_gen = rg.get_generator(args.judge_model)

        caching_status = "enabled" if args.enable_caching else "disabled"
        tools_status = "enabled" if args.enable_tools else "disabled"
        if args.enable_tools:
            logger.info(f"Tools configured: {[tool.__name__ for tool in BASIC_TOOLS]}")
        logger.info(
            f"Starting multi-agent recipe system with {args.num_requests} request(s)... (caching {caching_status}, tools {tools_status})",
        )

        # Track overall results
        all_results = []
        total_score = 0
        passed_count = 0

        for request_num in range(1, args.num_requests + 1):
            logger.info(f"--- Processing request {request_num}/{args.num_requests} ---")

            try:
                with dn.task_span(f"Request {request_num}"):
                    # Step 1: Request agent asks for recipe
                    with dn.task_span(f"Requester Agent {request_num}"):
                        recipe_request = await request_gluten_free_recipe(
                            requester_gen,
                            args.enable_caching,
                        )
                        dn.log_output(f"recipe_request_{request_num}", recipe_request)

                    # Step 2: Recipe generator creates the recipe
                    with dn.task_span(f"Recipe Generator Agent {request_num}"):
                        recipe, tool_calls_made = await generate_recipe(
                            recipe_gen,
                            recipe_request,
                            args.enable_caching,
                            args.enable_tools,
                        )
                        dn.log_output(f"generated_recipe_{request_num}", recipe)

                        if args.enable_tools:
                            dn.log_metric("tools_enabled", 1, step=request_num)
                            dn.log_metric("tools_configured", 1, step=request_num)
                            dn.log_metric("tool_calls_made", tool_calls_made, step=request_num)
                            if tool_calls_made > 0:
                                dn.log_metric("tools_actually_used", 1, step=request_num)
                            else:
                                dn.log_metric("tools_available_but_unused", 1, step=request_num)
                        else:
                            dn.log_metric("tools_disabled", 1, step=request_num)

                    # Step 3: Judge evaluates ingredients
                    with dn.task_span(f"Judge Agent {request_num}"):
                        evaluation = await judge_gluten_free_ingredients(
                            judge_gen,
                            recipe,
                            args.enable_caching,
                        )
                        dn.log_output(f"ingredient_evaluation_{request_num}", evaluation)

                        # Log structured evaluation results
                        logger.info(f"Judge evaluation results for request {request_num}:")
                        logger.info(f"  Score: {evaluation['score']}/100")
                        logger.info(f"  Gluten-free: {evaluation['is_gluten_free']}")
                        logger.info(f"  Detailed evaluation: {evaluation['evaluation']}")

                        dn.log_metric(f"gluten_free_score_{request_num}", evaluation["score"])
                        dn.log_metric(
                            f"is_gluten_free_{request_num}",
                            1 if evaluation["is_gluten_free"] else 0,
                        )
                        dn.log_metric("recipe_generated", 1, mode="count")

                        # Log normalized score as a metric (0-1 range for better dreadnode visualization)
                        dn.log_metric(
                            "gluten_free_compliance_normalized",
                            evaluation["score"] / 100.0,
                            step=request_num,
                        )

                        # Track aggregated results
                        result = {
                            "request_num": request_num,
                            "recipe": recipe,
                            "score": evaluation["score"],
                            "passed": evaluation["is_gluten_free"],
                            "evaluation": evaluation["evaluation"],
                        }
                        all_results.append(result)
                        total_score += evaluation["score"]
                        if evaluation["is_gluten_free"]:
                            passed_count += 1

                logger.success(f"Request {request_num} complete! Score: {evaluation['score']}/100")

            except (RuntimeError, ValueError, AttributeError) as e:
                logger.error(f"Request {request_num} failed: {e}")
                dn.log_metric("system_failed", 1, mode="count")
                continue

        # Final aggregated summary
        if all_results:
            avg_score = total_score / len(all_results)
            pass_rate = (passed_count / len(all_results)) * 100

            logger.success("=== FINAL SUMMARY ===")
            logger.success(f"Total requests processed: {len(all_results)}")
            logger.success(f"Average gluten-free score: {avg_score:.1f}/100")
            logger.success(
                f"Pass rate (≥80 score): {pass_rate:.1f}% ({passed_count}/{len(all_results)})",
            )

            # Add dynamic tags based on results (following dreadnode best practices)
            if avg_score >= 90:
                dn.tag("high-quality-recipes", to="run")
            elif avg_score >= 70:
                dn.tag("medium-quality-recipes", to="run")
            else:
                dn.tag("low-quality-recipes", to="run")

            if pass_rate >= 80:
                dn.tag("high-success-rate", to="run")
            elif pass_rate >= 50:
                dn.tag("medium-success-rate", to="run")
            else:
                dn.tag("low-success-rate", to="run")

            # Log aggregated metrics
            dn.log_metric("average_score", avg_score, to="run")
            dn.log_metric("pass_rate", pass_rate, to="run")
            dn.log_metric("total_requests", len(all_results), to="run")
            dn.log_metric("passed_requests", passed_count, to="run")

            # Log all results
            dn.log_output("all_results", all_results, to="run")
        else:
            logger.error("No requests completed successfully")
            dn.log_metric("total_failures", args.num_requests, to="run")

    logger.info("Done.")


if __name__ == "__main__":
    app()
