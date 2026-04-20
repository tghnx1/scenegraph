# Read this first!

Install the necessary parts first before pulling files from the branch.

## Requirements
```sh
$ node --version  
v20.20.2
$ npm --version
10.8.2
```
## Step by step
```sh
$ npm create vite@latest frontend -- --template react-ts
// y to proceed
// yes to install with npm and start now
// o + enter to test default page in browser
// q + enter to quit
```

That creates ./frontend directory and starts the vite project there. 

Then install the other things.
```sh
$ cd frontend
$ npm install react-router-dom zustand react-force-graph-2d

```

## Test the frontend

```sh
$ npm run dev
```

That would just test the default vite page again. 
Replace the content of ./frontend with the content of this directory.

## Notes
- used mock data instead of direct request to backend to avoid having 502 errors. 
	- click on artists to display artist page (again just a mock data).
	- the map tab is just a placeholder, can be a link to a dashboard (maybe).
- gallery of [react-force-graph](https://github.com/vasturiano/react-force-graph)
	- alternatives:
		- [vis network](https://visjs.github.io/vis-network/examples/)
		- [d3.js](https://observablehq.com/@d3/gallery?utm_source=d3js-org&utm_medium=hero&utm_campaign=try-observable#networks)
		- [cytoscape.js](https://js.cytoscape.org/#demos)
