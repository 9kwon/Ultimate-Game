const fs = require("fs");
const path = require("path");

exports.handler = async function(event) {
  if (event.httpMethod !== "POST") {
    return { statusCode: 405, body: "Method Not Allowed" };
  }

  try {
    const data = JSON.parse(event.body);
    const filename = `result_${Date.now()}.json`;
    const filepath = path.join("/tmp", filename);

    fs.writeFileSync(filepath, JSON.stringify(data, null, 2));

    return {
      statusCode: 200,
      body: `Saved result to ${filename}`
    };
  } catch (error) {
    return {
      statusCode: 500,
      body: `Error saving result: ${error.message}`
    };
  }
};
