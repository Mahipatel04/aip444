import dotenv from "dotenv";
import path from "path";

dotenv.config({ path: path.resolve("../../.env") });

const now = new Date();

console.log("git-cm: Developed by Mahi - 162637227");
console.log(`Run Date: ${now.toLocaleString()}`);
console.log("--------------------------------------------------------------");

const apiKey = process.env.OPENROUTER_API_KEY;

console.log("DEBUG KEY:", apiKey); // temporary debug line

if (!apiKey) {
  console.log("❌ Error: OPENROUTER_API_KEY not found");
  process.exit(1);
}

console.log("✅ API Key loaded successfully");