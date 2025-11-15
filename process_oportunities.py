"""Convert raw opportunity text snippets into structured JSON files."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, TypedDict

from langgraph.graph import END, StateGraph
from langchain_openai import ChatOpenAI


BASE_DIR = Path(__file__).resolve().parent
INDEX_DIR = BASE_DIR / "index"


class OpportunityState(TypedDict, total=False):
	file_name: str
	raw_text: str
	extracted: Dict[str, Any]
	normalized: Dict[str, Any]


def load_reference_list(path: Path, label: str) -> List[str]:
	"""Load a simple list of reference terms from JSON."""

	if not path.exists():
		raise FileNotFoundError(f"Missing {label} file at {path}")

	raw = path.read_text(encoding="utf-8").strip()
	if not raw:
		print(f"Warning: {label} file at {path} is empty.")
		return []

	try:
		data = json.loads(raw)
	except json.JSONDecodeError as exc:
		raise ValueError(f"{label} file must contain a JSON list") from exc

	if not isinstance(data, list):
		raise ValueError(f"{label} file must contain a JSON list")

	cleaned = []
	for item in data:
		if isinstance(item, str):
			value = item.strip()
		else:
			value = str(item).strip()
		if value:
			cleaned.append(value)

	if not cleaned:
		print(f"Warning: {label} list from {path} did not contain any usable entries.")

	return cleaned


def build_processing_graph(
	allowed_skills: List[str],
	allowed_interests: List[str],
	*,
	model_name: str = "gpt-5.1",
	temperature: float = 0.2,
):
	"""Create a LangGraph app that extracts normalized opportunity JSON."""

	llm = ChatOpenAI(model=model_name, temperature=temperature)
	skill_map = {skill.lower(): skill for skill in allowed_skills}
	interest_map = {interest.lower(): interest for interest in allowed_interests}

	def _match_token(token: str, allowed_map: Dict[str, str]) -> str | None:
		token = token.strip().lower()
		if not token or not allowed_map:
			return None
		if token in allowed_map:
			return allowed_map[token]
		for key, value in allowed_map.items():
			if token in key or key in token:
				return value
		return None

	def _filter_list(values: List[Any] | None, allowed_map: Dict[str, str]) -> List[str]:
		filtered: List[str] = []
		if not values:
			return filtered
		for raw_value in values:
			text = str(raw_value).strip()
			match = _match_token(text, allowed_map)
			if match and match not in filtered:
				filtered.append(match)
		return filtered

	def extract_opportunity(state: OpportunityState) -> OpportunityState:
		raw_text = state.get("raw_text", "").strip()
		file_name = state.get("file_name", "unknown")

		prompt = f"""
You convert volunteer opportunity descriptions into JSON.

Use only these skills when possible:
{', '.join(allowed_skills) if allowed_skills else 'No skills provided'}

Use only these interest areas when possible:
{', '.join(allowed_interests) if allowed_interests else 'No interests provided'}

Source file: {file_name}

Opportunity text:
---
{raw_text}
---

Return ONLY valid JSON with this exact shape:
{{
  "title": string,
  "description": string,
  "skills": [string, ...],
  "interests": [string, ...]
}}

Rules:
- Stay concise and factual.
- Prefer skills/interests from the provided lists; omit ones you cannot map.
- If info is missing, leave arrays empty rather than inventing details.
"""

		try:
			response = llm.invoke(prompt)
			extracted = json.loads(response.content)
			if not isinstance(extracted, dict):
				raise ValueError("LLM response was not a JSON object")
		except Exception as exc:
			print(f"Failed to parse LLM output for {file_name}: {exc}")
			extracted = {
				"title": file_name,
				"description": raw_text[:400],
				"skills": [],
				"interests": [],
			}

		return {"extracted": extracted}

	def normalize_opportunity(state: OpportunityState) -> OpportunityState:
		extracted = state.get("extracted", {})
		raw_text = state.get("raw_text", "").strip()
		file_name = state.get("file_name", "unknown")

		normalized = {
			"title": (extracted.get("title") or file_name).strip(),
			"description": (extracted.get("description") or raw_text[:800]).strip(),
			"skills": _filter_list(extracted.get("skills"), skill_map),
			"interests": _filter_list(extracted.get("interests"), interest_map),
			"source_file": file_name,
			"model": model_name,
		}

		if not normalized["description"]:
			normalized["description"] = "Description unavailable."

		if raw_text:
			normalized["source_excerpt"] = raw_text[:1200]

		return {"normalized": normalized}

	graph = StateGraph(OpportunityState)
	graph.add_node("extract", extract_opportunity)
	graph.add_node("normalize", normalize_opportunity)
	graph.set_entry_point("extract")
	graph.add_edge("extract", "normalize")
	graph.add_edge("normalize", END)

	return graph.compile()


def compute_thumbprint(text: str) -> str:
	"""Return a stable hash for the given text."""

	return hashlib.sha256(text.encode("utf-8")).hexdigest()


def append_to_index(index: Dict[str, List[Dict[str, str]]], keys: List[str], entry: Dict[str, str]) -> None:
	for key in keys or []:
		if not key:
			continue
		cleaned = str(key).strip()
		if not cleaned:
			continue
		index.setdefault(cleaned, []).append(entry)


def build_indexes_from_outputs(output_dir: Path) -> tuple[
	Dict[str, List[Dict[str, str]]],
	Dict[str, List[Dict[str, str]]],
]:
	skill_index: Dict[str, List[Dict[str, str]]] = {}
	interest_index: Dict[str, List[Dict[str, str]]] = {}

	for path in output_dir.glob("*.json"):
		if path.name.endswith(".idx.json"):
			continue
		try:
			data = json.loads(path.read_text(encoding="utf-8"))
		except json.JSONDecodeError:
			continue

		entry = {
			"title": str(data.get("title") or path.stem),
			"file": path.name,
			"source_file": str(data.get("source_file") or path.stem),
		}

		append_to_index(skill_index, data.get("skills") or [], entry)
		append_to_index(interest_index, data.get("interests") or [], entry)

	return skill_index, interest_index


def write_index_file(path: Path, label: str, index: Dict[str, List[Dict[str, str]]], generated_at: str) -> None:
	sorted_index = {
		term: sorted(entries, key=lambda item: item["title"].lower())
		for term, entries in sorted(index.items(), key=lambda item: item[0].lower())
	}
	payload = {
		"label": label,
		"generated_at": generated_at,
		"total_terms": len(sorted_index),
		"index": sorted_index,
	}
	path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
	print(f"Wrote {path.relative_to(BASE_DIR)}")


def process_opportunity_files(
	raw_dir: Path,
	output_dir: Path,
	skills_path: Path,
	interests_path: Path,
	model_name: str,
) -> None:
	skills = load_reference_list(skills_path, "skills")
	interests = load_reference_list(interests_path, "interests")

	txt_files = sorted(raw_dir.glob("*.txt"))
	if not txt_files:
		print(f"No .txt files found in {raw_dir}; nothing to process.")
		return

	graph = None
	output_dir.mkdir(parents=True, exist_ok=True)

	for txt_file in txt_files:
		raw_text = txt_file.read_text(encoding="utf-8")
		thumbprint = compute_thumbprint(raw_text)
		output_path = output_dir / f"{txt_file.stem}.json"

		if output_path.exists():
			try:
				existing = json.loads(output_path.read_text(encoding="utf-8"))
			except json.JSONDecodeError:
				existing = None

			if isinstance(existing, dict) and existing.get("thumbprint") == thumbprint:
				print(f"Skipping {txt_file.name}; thumbprint unchanged.")
				continue

		if graph is None:
			graph = build_processing_graph(skills, interests, model_name=model_name)

		state = graph.invoke({
			"file_name": txt_file.stem,
			"raw_text": raw_text,
		})
		normalized = state.get("normalized")
		if not normalized:
			print(f"Graph did not return normalized data for {txt_file.name}; skipping.")
			continue

		normalized["thumbprint"] = thumbprint

		with output_path.open("w", encoding="utf-8") as fh:
			json.dump(normalized, fh, indent=2)
		print(f"Wrote {output_path.relative_to(BASE_DIR)}")

	skill_index, interest_index = build_indexes_from_outputs(output_dir)
	generated_at = datetime.now(timezone.utc).isoformat()
	INDEX_DIR.mkdir(parents=True, exist_ok=True)
	write_index_file(INDEX_DIR / "skill.idx.json", "skills", skill_index, generated_at)
	write_index_file(INDEX_DIR / "interest.idx.json", "interests", interest_index, generated_at)


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Process raw opportunity text files into JSON.")
	parser.add_argument(
		"--raw-dir",
		type=Path,
		default=BASE_DIR / "oportunities_raw",
		help="Directory containing input .txt files.",
	)
	parser.add_argument(
		"--output-dir",
		type=Path,
		default=BASE_DIR / "oportunities",
		help="Directory where JSON files will be written.",
	)
	parser.add_argument(
		"--skills",
		type=Path,
		default=BASE_DIR / "skills.json",
		help="Path to skills JSON list.",
	)
	parser.add_argument(
		"--interests",
		type=Path,
		default=BASE_DIR / "interest.json",
		help="Path to interests JSON list.",
	)
	parser.add_argument(
		"--model",
		type=str,
		default="gpt-5.1",
		help="OpenAI-compatible chat model to use via langgraph-openai.",
	)
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	process_opportunity_files(
		raw_dir=args.raw_dir,
		output_dir=args.output_dir,
		skills_path=args.skills,
		interests_path=args.interests,
		model_name=args.model,
	)


if __name__ == "__main__":
	main()
