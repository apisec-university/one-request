#!/bin/bash
set -e

SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
BASE_DIR=$(dirname "$SCRIPT_DIR")
BUILD_DIR="$BASE_DIR/build"
TEMP_FILE=$(mktemp --suffix=.json)

mkdir -p "$BUILD_DIR"

python3 "$BASE_DIR/scripts/generate-openapi-spec.py" -o "$BUILD_DIR/openapi.json"

#npm install -g openapi2postmanv2
npx openapi2postmanv2 --spec "$BUILD_DIR/openapi.json" --pretty --output "$TEMP_FILE"

overrides=$(cat "$BASE_DIR/scripts/postmanOverrides.json")

# patch generated json
cat "$TEMP_FILE" |
  # remove default baseUrl variable
  jq '.variable |= map(select(.key != "baseUrl"))' |
  # add variable overrides
  jq --argjson overrides "$overrides" '.variable += $overrides.variable' |
  # add info overrides
  jq --argjson overrides "$overrides" '.info = $overrides.info' |
  # remove oauth from each endpoint
  jq 'walk(
    if type == "object" and has("auth") then
      if .auth.type == "oauth2"
        then .auth = null
        else .auth = {"type": "noauth"}
      end
    else . end)' |
  # add auth overrides
  jq --argjson overrides "$overrides" '.auth = $overrides.auth' > "$BUILD_DIR/postman.json"
#  jq 'walk(
#    if type == "object" and .key == "x-group-id" and .value == "<string>"
#    then .value = "{{groupId}}"
#    else . end)' > "$BUILD_DIR/postman.json"

rm "$TEMP_FILE"
echo "Postman collection generated at $BUILD_DIR/postman.json"