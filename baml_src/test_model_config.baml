

enum Choices {
    Dog
    Cat
    Table
}

class TextTestStructuredResponse {
   correct_choice Choices
}

function TextTestStructured(activity_name: string,
                     activity_description: string,
                     tag_catalog: Tag[]) -> TextTestStructuredResponse {
  client "TextClient"            // choose a concrete client at call-time

  prompt #"
    {{ _.role("system") }}
    Choose the choice that corresponds to something that is not a living thing.

    {{ _.role("user") }}
  {{ ctx.output_format }}
  "#
                     }

enum ImageClassificationChoices {
    Car
    Tree
    House
}

class ImageClassificationResponse {
   correct_choice ImageClassificationChoices
}

function TextTestUnstructured() -> string {
  client "TextClient"            // choose a concrete client at call-time

  prompt #"
    {{ _.role("system") }}

    What is the name of a domestic animal that barks?

    {{ _.role("user") }}
  Please respond with the answer directly, without any additional text.
  "#
                     }

function ImageTestStructured() -> TextTestStructuredResponse {
  client "ImageClient"            // choose a concrete client at call-time

    prompt #"
        {{ _.role("system") }}
        Classify the following image into one of the available choices.

        {{ _.role("user") }}
    {{ ctx.output_format }}
        "#
                     }


function ImageTestUnstructured() -> string {
  client "ImageClient"            // choose a concrete client at call-time
    prompt #"
        {{ _.role("system") }}

        What is shown in the following image? The choices are: Car, Tree, House.
        Respond with only one of these choices.

        {{ _.role("user") }}
    Please respond with the answer directly, without any additional text.
        "#
                     }
