# Project Plan: Resource Availability Chat Interface

## Overview
The project aims to create a chat interface using Streamlit that allows users to query the availability of resources (employees) based on the data stored in Firebase. The system will use LlamaIndex agents to process user queries, interact with Firebase APIs, and provide intelligent responses, including recommendations for alternative resources or dates if the exact match is not found.

---

## Functional Specifications

### 1. **User Interface (Streamlit)**
- **Chat Interface**: A simple chat interface where users can input their queries.
- **Query Types**:
  - Find available resources by skill, location, and date range.
  - Check specific employee availability.
  - Request recommendations for alternative resources or dates.
- **Response Display**: Display results in a user-friendly format, including:
  - Available resources.
  - Alternative recommendations (if exact match not found).
  - Nearest availability dates.

### 2. **Backend (LlamaIndex Agents)**
- **Agents**:
  1. **Query Parser Agent**: 
     - Parses user queries to extract key parameters (skills, location, dates, etc.).
     - Determines the intent of the query (e.g., find availability, recommend alternatives).
  2. **Firebase Data Fetcher Agent**:
     - Makes API calls to Firebase to fetch employee and availability data.
     - Filters data based on the parsed query parameters.
  3. **Resource Matcher Agent**:
     - Matches resources based on skills, location, and availability.
     - Identifies exact matches or partial matches.
  4. **Recommendation Agent**:
     - Analyzes data to recommend:
       - Alternative resources with similar skills.
       - Nearest availability dates if exact dates are unavailable.
  5. **Response Generator Agent**:
     - Formats the results into a user-friendly response.
     - Provides explanations for recommendations.

### 3. **Firebase Integration**
- **Employee Data**:
  - Query employees by skills, location, and rank.
- **Availability Data**:
  - Query availability by employee ID and date range.
- **API Calls**:
  - Two web service calls:
    1. Fetch employee data (skills, location, rank).
    2. Fetch availability data (8 weeks of availability per employee).

### 4. **Autonomous Agent Workflow**
1. **User Query**: User inputs a query in the chat interface.
2. **Query Parsing**: The Query Parser Agent extracts parameters and intent.
3. **Data Fetching**: The Firebase Data Fetcher Agent retrieves relevant data from Firebase.
4. **Resource Matching**: The Resource Matcher Agent finds exact or partial matches.
5. **Recommendation**: The Recommendation Agent analyzes data for alternatives.
6. **Response Generation**: The Response Generator Agent formats and displays the results.

---

## Agent Breakdown

### 1. **Query Parser Agent**
- **Input**: User query (text).
- **Output**: Structured query parameters (skills, location, dates, intent).

### 2. **Firebase Data Fetcher Agent**
- **Input**: Structured query parameters.
- **Output**: Filtered employee and availability data.

### 3. **Resource Matcher Agent**
- **Input**: Filtered employee and availability data.
- **Output**: Exact or partial matches for the query.

### 4. **Recommendation Agent**
- **Input**: Partial matches or no matches.
- **Output**: Recommendations for alternative resources or dates.

### 5. **Response Generator Agent**
- **Input**: Matches and recommendations.
- **Output**: User-friendly response with explanations.

---

## Technical Stack
- **Frontend**: Streamlit (chat interface).
- **Backend**: LlamaIndex (autonomous agents).
- **Data Storage**: Firebase (employee and availability data).
- **APIs**: Firebase REST API for data fetching.

---

## Workflow Diagram 