# Read this first!

Install the necessary parts first before pulling files from the branch.

## Requirements
```sh
$> node --version
v20.20.2
$> npm --version
10.8.2
```

## Install modules/components
```sh
$> npm install
```

## Test the page

```sh
$> npm run dev
// h then enter
```

## Notes
- used mock data instead of direct request to backend to avoid having 502 errors.
	- click on artists to display artist page (again just a mock data).
	- the map tab is just a placeholder, can be a link to a dashboard (maybe).
- gallery of [react-force-graph](https://github.com/vasturiano/react-force-graph)
	- alternatives:
		- [vis network](https://visjs.github.io/vis-network/examples/)
		- [d3.js](https://observablehq.com/@d3/gallery?utm_source=d3js-org&utm_medium=hero&utm_campaign=try-observable#networks)
		- [cytoscape.js](https://js.cytoscape.org/#demos)
