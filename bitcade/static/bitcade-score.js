(function () {
  function submitScore(score) {
    if (!score || typeof score !== "object") {
      throw new Error("Bitcade score must be an object.");
    }
    window.parent.postMessage(
      Object.assign({ type: "bitcade:score" }, score),
      window.location.origin
    );
  }

  window.Bitcade = Object.assign({}, window.Bitcade || {}, { submitScore });
})();
