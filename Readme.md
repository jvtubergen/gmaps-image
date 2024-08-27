# Google Maps image retriever

Retrieving arbitrary sized Google Maps images at the zoom level and scale of choice.
Requires a Google Maps API key to retrieve images from Google Maps (and thus to use this library).
Uses an image cache to minimize fetch requests, currently hard-coded to be stored at `$HOME/.cache/gmaps-image`.

Further properties:
* Automatically pad and remove google logo for constructing larger images beyond public image API.
* Stick to custom image tiling size (taking cut size into consideration).
* Cache fetched images from to only retrieve pixel data of a geolocation once.
Using caching for retrieving an image tile only once.
