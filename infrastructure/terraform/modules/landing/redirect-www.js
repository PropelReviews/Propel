// CloudFront viewer-request function: 301 any www.* host to its apex so the
// landing site has a single canonical URL (e.g. www.propel.ninja ->
// propel.ninja). Works for prod and beta without configuration because it just
// strips the leading "www." label.
function handler(event) {
  var request = event.request;
  var host = request.headers.host.value;

  if (host.startsWith("www.")) {
    var apex = host.slice(4);
    return {
      statusCode: 301,
      statusDescription: "Moved Permanently",
      headers: {
        location: { value: "https://" + apex + request.uri },
      },
    };
  }

  return request;
}
