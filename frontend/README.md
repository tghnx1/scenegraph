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
$> npm ci
```

## Test the page

```sh
$> npm run dev
// h then enter
```

## Notes
- used mock data instead of direct request to backend to avoid having 502 errors.
	- click on artists to display artist page (again just a mock data).
- merge with main 28.4.26 --> change nginx to 8080:80
	- so after make up, go to http://localhost:8080