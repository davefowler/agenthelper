# GitHub PR Simplifier

A Chrome extension that simplifies GitHub pull request pages by reducing comment clutter and providing a cleaner interface.

## Features

- **Clean CI/Merge View**: Shows CI action status and merge button prominently at the top
- **Tabbed Comments**: All comments displayed in a tabbed interface, stacked with newest on top
- **Quick Navigation**: Easily switch between comments without endless scrolling
- **Toggle View**: Switch between simplified and original GitHub view with one click
- **Dark Mode Support**: Automatically adapts to your system/GitHub theme preference

## Installation

1. Open Chrome and go to `chrome://extensions/`
2. Enable "Developer mode" (toggle in top-right corner)
3. Click "Load unpacked"
4. Select the `github-pr-simplifier` folder
5. Navigate to any GitHub PR page to see it in action

## Usage

- Visit any GitHub pull request page (e.g., `https://github.com/owner/repo/pull/123`)
- The extension automatically simplifies the view
- Click tabs on the left to switch between comments (newest first)
- Use the "Show Original View" button (top-right) to toggle back to standard GitHub view

## How It Works

The extension:
1. Extracts the CI status and merge controls from the PR page
2. Collects all timeline comments and sorts them by date (newest first)
3. Creates a tabbed interface where each tab represents a comment
4. Hides the original cluttered view while preserving all functionality
