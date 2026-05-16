import dotenv from "dotenv";
import path from "path";
import OpenAI from "openai";
import { execSync } from "child_process";

dotenv.config({ path: path.resolve("../../.env") });

const now = new Date();

console.log("git-cm: Developed by Mahi - 162637227");
console.log(`Run Date: ${now.toLocaleString()}`);
console.log("--------------------------------------------------------------");

// Detect creative mode
const isCreative = process.argv.includes("--creative");

const apiKey = process.env.OPENROUTER_API_KEY;

if (!apiKey) {
  console.log("❌ Error: OPENROUTER_API_KEY not found");
  process.exit(1);
}

console.log("✅ API Key loaded successfully");

const client = new OpenAI({
  baseURL: "https://openrouter.ai/api/v1",
  apiKey: apiKey,
});

// Get staged git diff
const diff = execSync("git diff --staged").toString();

if (!diff) {
  console.log("❌ No staged changes found");
  process.exit(0);
}

console.log(`✅ Diff found: ${diff.length} characters`);

// Default system prompt
let systemPrompt = `
You are an LLM running in a CLI tool that writes git commit messages.

You will be given a git diff.

Return ONLY a conventional commit message.
No explanations.
No markdown.
No quotes.

Example:
feat: add login button
fix(auth): handle null user error
`;

// Default temperature
let temperature = 0.1;

// Creative mode changes
if (isCreative) {
  console.log("🎨 Creative Mode Enabled");

  systemPrompt = `
You are a pirate programmer from the 17th century.

Write funny git commit messages using pirate slang and Gitmoji.

Return ONLY the commit message.

Examples:
🏴‍☠️ feat: add shiny new treasure map
🦜 fix: patch leaky ship code matey
`;

  temperature = 1.5;
}

const main = async () => {
  try {
    const response = await client.chat.completions.create({
      model: "openai/gpt-4.1-nano",
      temperature: temperature,
      messages: [
        {
          role: "system",
          content: systemPrompt,
        },
        {
          role: "user",
          content: diff,
        },
      ],
    });

    const commitMessage = response.choices[0].message.content;

    console.log("\n🤖 Generated Commit Message:");
    console.log(commitMessage);

  } catch (err) {
    console.log("❌ Error generating commit message");
    console.log(err.message);
  }
};
// creative mode test
main();