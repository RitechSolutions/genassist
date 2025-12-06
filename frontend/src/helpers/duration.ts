export function formatDuration(totalSecondsInput: number | string | null | undefined): string {
	if (totalSecondsInput === null || totalSecondsInput === undefined) {
		return "0:00";
	}

	const numeric = Number(totalSecondsInput);
	if (!Number.isFinite(numeric) || Number.isNaN(numeric)) {
		return "0:00";
	}

	const totalSeconds = Math.max(0, Math.floor(numeric));
	const hours = Math.floor(totalSeconds / 3600);
	const minutes = Math.floor((totalSeconds % 3600) / 60);
	const seconds = totalSeconds % 60;

	if (hours > 0) {
		return `${hours}:${minutes.toString().padStart(2, "0")}:${seconds
			.toString()
			.padStart(2, "0")}`;
	}

	return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export default formatDuration;


