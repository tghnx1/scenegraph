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
