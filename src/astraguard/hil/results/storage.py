"""Test result persistence and retrieval.

This module provides functionality for storing and retrieving test results
from Hardware-in-the-Loop (HIL) simulations. It includes the ResultStorage class
for managing result files, campaign summaries, and aggregate statistics.

Classes:
    ResultStorage: Handles saving, loading, and managing test result data.
"""

import asyncio
import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, cast


logger: logging.Logger = logging.getLogger(__name__)


class ResultStorage:
    """Manages persistent storage and retrieval of test results.

    This class provides methods to save individual scenario results, retrieve
    results for specific scenarios or campaigns, and compute aggregate statistics.
    Results are stored as JSON files in a specified directory.

    Attributes:
        results_dir (Path): Directory where result files are stored.
    """

    def __init__(self, results_dir: str = "astraguard/hil/results") -> None:
        """
        Initialize result storage.

        Args:
            results_dir (str): Directory for result files.
        """
        self.results_dir: Path = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def _check_disk_space(self, required_mb: int = 10) -> bool:
        """Check if sufficient disk space is available.
        
        Args:
            required_mb: Minimum required space in MB
            
        Returns:
            bool: True if sufficient space available
        """
        try:
            import shutil
            stat = shutil.disk_usage(self.results_dir)
            available_mb = stat.free / (1024 * 1024)
            
            if available_mb < required_mb:
                logger.warning(
                    f"Low disk space: {available_mb:.2f}MB available, {required_mb}MB required",
                    extra={"available_mb": available_mb, "required_mb": required_mb}
                )
                return False
            return True
        except (OSError, AttributeError) as e:
            logger.warning(f"Could not check disk space: {e}")
            return True  # Assume OK if check fails

    def _validate_result_structure(self, result: Dict[str, Any], scenario_name: str) -> str:
        """Validate result structure and serialize to JSON.
        
        Checks for common issues like unusual status values, invalid timestamp types,
        and non-serializable data (including circular references). Uses the same
        serialization settings as the write path to ensure consistency.
        
        Args:
            result: Result dictionary to validate
            scenario_name: Name of the scenario for context
            
        Returns:
            str: JSON-serialized result string (for reuse in write)
            
        Raises:
            ValueError: If result contains non-serializable or circular data
        """
        # Check for common result fields
        if "status" in result and result["status"] not in ["passed", "failed", "error", "skipped"]:
            logger.warning(
                f"Unusual status value in result: {result['status']}",
                extra={"scenario": scenario_name, "status": result["status"]}
            )
        
        # Validate timestamp if present
        if "timestamp" in result and not isinstance(result.get("timestamp"), (str, datetime)):
            raise ValueError(f"timestamp must be a string or datetime, got {type(result['timestamp'])}")
        
        # Serialization check using same settings as write path (default=str)
        # This validates against circular references while keeping behavior consistent
        try:
            return json.dumps(result, indent=2, default=str)
        except (TypeError, ValueError, RecursionError) as e:
            raise ValueError(f"Result contains non-serializable or circular data: {e}")

    async def save_scenario_result(
        self, scenario_name: str, result: Dict[str, Any]
    ) -> str:
        """
        Persist result data for a single HIL scenario execution.

        Saves the result dictionary as a JSON file, automatically appending
        timestamp metadata (`scenario_name_{timestamp}.json`).

        Args:
            scenario_name (str): Name of the test scenario (e.g., "power_loss_geo").
            result (Dict[str, Any]): The execution result object to save.

        Returns:
            str: The absolute path to the saved result file.

        Raises:
            OSError: If filesystem writes fail.
            ValueError: If input data is invalid or non-serializable.
        """
        if not scenario_name or not isinstance(scenario_name, str):
            raise ValueError(f"Invalid scenario_name: {scenario_name}")
        
        if not isinstance(result, dict):
            raise ValueError(f"Result must be a dictionary, got {type(result)}")

        timestamp: str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename: str = f"{scenario_name}_{timestamp}.json"
        filepath: Path = self.results_dir / filename

        # Ensure result has metadata
        result_with_metadata: Dict[str, Any] = {
            "scenario_name": scenario_name,
            "timestamp": datetime.now().isoformat(),
            **result,
        }

        # Validate and serialize result_with_metadata (reuse JSON string)
        json_str = self._validate_result_structure(result_with_metadata, scenario_name)

        if not self._check_disk_space():
            raise OSError("Insufficient disk space to save result")

        try:
            # Perform file write off the event loop to avoid blocking
            await asyncio.to_thread(filepath.write_text, json_str)
            logger.info(f"Saved scenario result: {filepath}")
            return str(filepath)
        except OSError as e:
            logger.error(
                f"Failed to write result file: {e}",
                extra={
                    "filepath": str(filepath),
                    "scenario": scenario_name,
                    "error_type": type(e).__name__,
                    "operation": "write"
                }
            )
            raise
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize result data for {scenario_name}: {e}")
            raise

    async def get_scenario_results(
        self, scenario_name: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieve recent results for a specific scenario.

        Args:
            scenario_name (str): Name of scenario.
            limit (int, optional): Maximum results to return. Defaults to 10.

        Returns:
            List[Dict[str, Any]]: List of result dicts (newest first).

        Raises:
            OSError: If there is an issue reading result files.
            json.JSONDecodeError: If a result file contains invalid JSON.
        """
        if not scenario_name or not isinstance(scenario_name, str):
            logger.warning(f"Invalid scenario_name: {scenario_name}")
            return []
        
        if limit <= 0:
            logger.warning(f"Invalid limit: {limit}")
            return []

        results: List[Dict[str, Any]] = []
        pattern: str = f"{scenario_name}_*.json"
        result_files: List[Path] = sorted(self.results_dir.glob(pattern), reverse=True)[:limit]

        async def load_result(result_file: Path):
            try:
                text = await asyncio.to_thread(result_file.read_text)
                result_data = cast(Dict[str, Any], json.loads(text))
                results.append(result_data)
            except (OSError, IOError, PermissionError) as e:
                logger.warning(f"Failed to read result file {result_file.name}: {e}")
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.warning(f"Corrupted result file {result_file.name}: {e}")
            except Exception as e:
                logger.error(
                    f"Unexpected error loading result {result_file.name}: {e}",
                    extra={"file": str(result_file), "scenario": scenario_name},
                    exc_info=True,
                )

        # Load files concurrently off the event loop
        await asyncio.gather(*(load_result(f) for f in result_files))
        return results

    async def get_recent_campaigns(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve recent campaign summaries asynchronously.

        Args:
            limit (int, optional): Maximum campaigns to return. Defaults to 10.

        Returns:
            List[Dict[str, Any]]: List of campaign summary dicts (newest first).

        Raises:
            OSError: If there is an issue reading campaign files.
            json.JSONDecodeError: If a campaign file contains invalid JSON.
        """
        if limit <= 0:
            logger.warning(f"Invalid limit: {limit}")
            return []

        campaigns: List[Dict[str, Any]] = []
        campaign_files: List[Path] = sorted(
            self.results_dir.glob("campaign_*.json"), reverse=True
        )[:limit]

        async def load_campaign(campaign_file):
            try:
                campaign_data = cast(Dict[str, Any], json.loads(campaign_file.read_text()))
                campaigns.append(campaign_data)
            except (OSError, IOError, PermissionError) as e:
                logger.warning(f"Failed to read campaign file {campaign_file.name}: {e}")
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.warning(f"Corrupted campaign file {campaign_file.name}: {e}")
            except Exception as e:
                # Log unexpected errors but continue processing other files (best-effort)
                logger.error(
                    f"Unexpected error loading campaign {campaign_file.name}: {e}",
                    extra={"file": str(campaign_file)},
                    exc_info=True
                )

        campaigns = await asyncio.gather(*[load_campaign(f) for f in campaign_files])
        return [c for c in campaigns if c is not None]

    async def get_campaign_summary(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve specific campaign by ID asynchronously.

        Args:
            campaign_id (str): Campaign timestamp ID (YYYYMMDD_HHMMSS).

        Returns:
            Optional[Dict[str, Any]]: Campaign summary dict or None if not found.

        Raises:
            OSError: If there is an issue reading the campaign file.
            json.JSONDecodeError: If the campaign file contains invalid JSON.
        """
        if not campaign_id or not isinstance(campaign_id, str):
            logger.warning(f"Invalid campaign_id: {campaign_id}")
            return None

        campaign_file: Path = self.results_dir / f"campaign_{campaign_id}.json"
        if not campaign_file.exists():
            return None

        try:
            return cast(Dict[str, Any], json.loads(campaign_file.read_text()))
        except (OSError, IOError, PermissionError) as e:
            logger.error(
                f"Failed to read campaign {campaign_id}: {e}",
                extra={"campaign_id": campaign_id, "error_type": type(e).__name__}
            )
            return None
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(
                f"Corrupted campaign file {campaign_id}: {e}",
                extra={"campaign_id": campaign_id}
            )
            return None
        except Exception as e:
            logger.critical(
                f"Critical unexpected error loading campaign {campaign_id}: {e}",
                exc_info=True
            )
            return None

    async def get_result_statistics(self) -> Dict[str, Any]:
        """Get aggregate statistics across all results asynchronously.

        Returns:
            Dict[str, Any]: Dict with statistics including total_campaigns,
                total_scenarios, total_passed, and avg_pass_rate.
        """
        campaigns: List[Dict[str, Any]] = await self.get_recent_campaigns(limit=999)
        if not campaigns:
            return {
                "total_campaigns": 0,
                "total_scenarios": 0,
                "avg_pass_rate": 0.0,
            }

        total_campaigns: int = len(campaigns)
        total_scenarios: int = sum(c.get("total_scenarios", 0) for c in campaigns)
        total_passed: int = sum(c.get("passed", 0) for c in campaigns)
        avg_pass_rate: float = total_passed / total_scenarios if total_scenarios > 0 else 0.0

        return {
            "total_campaigns": total_campaigns,
            "total_scenarios": total_scenarios,
            "total_passed": total_passed,
            "avg_pass_rate": avg_pass_rate,
        }

    async def clear_results(self, older_than_days: int = 30) -> int:
        """Remove old result files asynchronously.

        Args:
            older_than_days (int, optional): Delete files older than this many days. Defaults to 30.

        Returns:
            int: Number of files deleted.

        Raises:
            OSError: If there is an issue accessing or deleting files.
        """
        if older_than_days <= 0:
            logger.warning(f"Invalid age threshold: {older_than_days}")
            return 0

        from time import time

        cutoff_time: float = time() - (older_than_days * 86400)
        deleted_count: int = 0

        for result_file in self.results_dir.glob("*.json"):
            try:
                if result_file.stat().st_mtime < cutoff_time:
                    result_file.unlink()
                    deleted_count += 1
            except PermissionError as e:
                logger.warning(
                    f"Permission denied deleting file {result_file.name}: {e}",
                    extra={"file": str(result_file), "operation": "delete"}
                )
            except FileNotFoundError:
                # File already deleted, ignore
                pass
            except OSError as e:
                logger.error(
                    f"OS error deleting file {result_file.name}: {e}",
                    extra={"file": str(result_file), "error_code": e.errno}
                )
            except Exception as e:
                logger.critical(
                    f"Critical unexpected error deleting file {result_file.name}: {e}",
                    exc_info=True
                )

        logger.info(f"Cleanup completed: deleted {deleted_count} files older than {older_than_days} days")
        return deleted_count
