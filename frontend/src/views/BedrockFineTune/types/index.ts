export type S3FileRef = { s3_uri: string; name: string };

export type BedrockFineTuneJobsCardProps = {
  searchQuery: string;
  refreshKey?: number;
  onNewFineTuneJob?: () => void;
};
