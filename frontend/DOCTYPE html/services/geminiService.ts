import { GoogleGenAI } from "@google/genai";

const API_KEY = process.env.API_KEY || '';

export const analyzeFrame = async (base64Image: string): Promise<string> => {
  if (!API_KEY) {
    throw new Error("API Key is missing. Please set the API_KEY environment variable.");
  }

  try {
    const ai = new GoogleGenAI({ apiKey: API_KEY });
    
    // Remove data URL prefix if present
    const cleanBase64 = base64Image.replace(/^data:image\/(png|jpg|jpeg);base64,/, "");

    const response = await ai.models.generateContent({
      model: 'gemini-2.5-flash',
      contents: {
        parts: [
          {
            inlineData: {
              mimeType: 'image/png',
              data: cleanBase64
            }
          },
          {
            text: "Analyze this webcam frame as a computer vision system. Briefly identify the main foreground object and suggest where a segmentation mask should be applied. Format the response as a technical log entry."
          }
        ]
      }
    });

    return response.text || "No analysis generated.";
  } catch (error) {
    console.error("Gemini Analysis Error:", error);
    return "Error analyzing frame. Please try again.";
  }
};