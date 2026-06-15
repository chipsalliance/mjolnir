{
  name = "gemini-gcs-test";
  model = "gemini-2.5-flash";
  maxFiles = 5;
  srcDirs = [ "src" ];
  extensions = [ "rs" ];
  requireGcsUpload = true;
  provider = "genai";
}
